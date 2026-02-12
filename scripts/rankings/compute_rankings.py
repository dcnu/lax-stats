#!/usr/bin/env python3
"""
Compute team rankings: RPI, Massey, recency-weighted Massey, and Bayesian projected RPI.

Writes to team_season_rankings (current snapshot) and team_season_rankings_history
(weekly snapshots). All rankings are per-season.

Usage:
	python -m scripts.rankings.compute_rankings
	python -m scripts.rankings.compute_rankings --season 2025 --backfill
	python -m scripts.rankings.compute_rankings --dry-run
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_connection


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_season_info(cur, season_id):
	"""Load season metadata. Returns (season_id, start_date) or exits."""
	if season_id:
		cur.execute(
			"SELECT id, start_date FROM lookup_seasons WHERE id = %s",
			(season_id,),
		)
	else:
		cur.execute(
			"SELECT id, start_date FROM lookup_seasons WHERE is_current = true"
		)
	row = cur.fetchone()
	if not row:
		print(f"Error: season '{season_id or 'current'}' not found.", file=sys.stderr)
		sys.exit(1)
	return row["id"], row["start_date"]


def load_games(cur, season_id):
	"""Load all final games for the season."""
	cur.execute(
		"""SELECT id, home_team_id, away_team_id, home_score, away_score,
		          game_date, division_id
		   FROM games
		   WHERE season_id = %s AND status = 'final'
		   ORDER BY game_date""",
		(season_id,),
	)
	return cur.fetchall()


def load_remaining_games(cur, season_id):
	"""Load scheduled (non-final) games for Bayesian projections."""
	cur.execute(
		"""SELECT id, home_team_id, away_team_id
		   FROM games
		   WHERE season_id = %s AND status != 'final'""",
		(season_id,),
	)
	return cur.fetchall()


def load_prior_rankings(cur, season_id):
	"""Load prior season's RPI rankings for Bayesian seeding."""
	try:
		prior_id = str(int(season_id) - 1)
	except ValueError:
		return {}
	cur.execute(
		"SELECT team_id, rpi FROM team_season_rankings WHERE season_id = %s",
		(prior_id,),
	)
	return {r["team_id"]: float(r["rpi"]) for r in cur.fetchall() if r["rpi"]}


def load_team_names(cur):
	"""Load team_id → name mapping."""
	cur.execute("SELECT id, name FROM lookup_teams")
	return {r["id"]: r["name"] for r in cur.fetchall()}


def build_team_set(games):
	"""Extract unique team IDs from games."""
	teams = set()
	for g in games:
		teams.add(g["home_team_id"])
		teams.add(g["away_team_id"])
	return sorted(teams)


# ---------------------------------------------------------------------------
# Week derivation
# ---------------------------------------------------------------------------

def get_week1_monday(start_date):
	"""Week 1 starts on the first Monday >= start_date."""
	d = start_date
	while d.weekday() != 0:  # 0 = Monday
		d += timedelta(days=1)
	return d


def get_current_week(week1_monday):
	"""Current week number (1-based)."""
	delta = (date.today() - week1_monday).days
	if delta < 0:
		return 0
	return delta // 7 + 1


def filter_games_through_week(games, week1_monday, week_num):
	"""Return games played before end of given week."""
	cutoff = week1_monday + timedelta(days=7 * week_num)
	return [g for g in games if g["game_date"] < cutoff]


# ---------------------------------------------------------------------------
# RPI
# ---------------------------------------------------------------------------

def compute_rpi(games, teams):
	"""Compute RPI for each team.

	Returns dict of {team_id: {wp, owp, oowp, rpi, wins, losses}}.
	"""
	wins = defaultdict(int)
	losses = defaultdict(int)
	# opponents[team] = list of opponent IDs (one per game)
	opponents = defaultdict(list)
	# head-to-head: h2h[(a,b)] = (wins_a_vs_b, losses_a_vs_b)
	h2h_wins = defaultdict(int)
	h2h_losses = defaultdict(int)

	for g in games:
		h = g["home_team_id"]
		a = g["away_team_id"]
		hs, as_ = g["home_score"], g["away_score"]
		opponents[h].append(a)
		opponents[a].append(h)
		if hs > as_:
			wins[h] += 1
			losses[a] += 1
			h2h_wins[(h, a)] += 1
			h2h_losses[(a, h)] += 1
		elif as_ > hs:
			wins[a] += 1
			losses[h] += 1
			h2h_wins[(a, h)] += 1
			h2h_losses[(h, a)] += 1

	# WP
	wp = {}
	for t in teams:
		total = wins[t] + losses[t]
		wp[t] = wins[t] / total if total > 0 else 0.0

	# OWP: opponent's WP excluding head-to-head games against team
	owp = {}
	for t in teams:
		opp_wps = []
		for opp in opponents[t]:
			opp_total = wins[opp] + losses[opp]
			# remove h2h games between opp and t
			adj_wins = wins[opp] - h2h_wins.get((opp, t), 0)
			adj_losses = losses[opp] - h2h_losses.get((opp, t), 0)
			adj_total = adj_wins + adj_losses
			if adj_total > 0:
				opp_wps.append(adj_wins / adj_total)
		owp[t] = np.mean(opp_wps) if opp_wps else 0.0

	# OOWP
	oowp = {}
	for t in teams:
		opp_owps = [owp[opp] for opp in opponents[t] if opp in owp]
		oowp[t] = np.mean(opp_owps) if opp_owps else 0.0

	result = {}
	for t in teams:
		rpi = 0.25 * wp[t] + 0.50 * owp[t] + 0.25 * oowp[t]
		result[t] = {
			"wp": round(wp[t], 6),
			"owp": round(owp[t], 6),
			"oowp": round(oowp[t], 6),
			"rpi": round(rpi, 6),
			"wins": wins[t],
			"losses": losses[t],
		}
	return result


# ---------------------------------------------------------------------------
# Massey
# ---------------------------------------------------------------------------

def compute_massey(games, teams):
	"""Massey ranking via least squares on score margins (clamped ±8).

	Returns dict of {team_id: ranking}.
	"""
	if len(teams) < 2 or len(games) < len(teams):
		return {t: 0.0 for t in teams}

	idx = {t: i for i, t in enumerate(teams)}
	n = len(teams)
	m = len(games)

	M = np.zeros((m, n))
	d = np.zeros(m)

	for k, g in enumerate(games):
		hi = idx[g["home_team_id"]]
		ai = idx[g["away_team_id"]]
		margin = g["home_score"] - g["away_score"]
		margin = max(-8, min(8, margin))
		M[k, hi] = 1
		M[k, ai] = -1
		d[k] = margin

	# Normal equations: (M^T M) r = M^T d
	MtM = M.T @ M
	Mtd = M.T @ d

	# Replace last row with sum-to-zero constraint
	MtM[-1, :] = 1
	Mtd[-1] = 0

	try:
		r = np.linalg.solve(MtM, Mtd)
	except np.linalg.LinAlgError:
		r, _, _, _ = np.linalg.lstsq(MtM, Mtd, rcond=None)

	return {t: round(float(r[idx[t]]), 6) for t in teams}


def compute_massey_recency(games, teams, season_start):
	"""Massey with exponential recency weighting.

	Weight: w_k = exp(-0.02 * (t_max - t_k)) where t_k = days since season start.
	Returns dict of {team_id: ranking}.
	"""
	if len(teams) < 2 or len(games) < len(teams):
		return {t: 0.0 for t in teams}

	idx = {t: i for i, t in enumerate(teams)}
	n = len(teams)
	m = len(games)

	M = np.zeros((m, n))
	d = np.zeros(m)
	days = np.zeros(m)

	for k, g in enumerate(games):
		hi = idx[g["home_team_id"]]
		ai = idx[g["away_team_id"]]
		margin = g["home_score"] - g["away_score"]
		margin = max(-8, min(8, margin))
		M[k, hi] = 1
		M[k, ai] = -1
		d[k] = margin
		days[k] = (g["game_date"] - season_start).days

	t_max = days.max() if m > 0 else 0
	weights = np.exp(-0.02 * (t_max - days))
	W = np.diag(weights)

	MtWM = M.T @ W @ M
	MtWd = M.T @ W @ d

	# Sum-to-zero constraint
	MtWM[-1, :] = 1
	MtWd[-1] = 0

	try:
		r = np.linalg.solve(MtWM, MtWd)
	except np.linalg.LinAlgError:
		r, _, _, _ = np.linalg.lstsq(MtWM, MtWd, rcond=None)

	return {t: round(float(r[idx[t]]), 6) for t in teams}


# ---------------------------------------------------------------------------
# Bayesian projected RPI
# ---------------------------------------------------------------------------

def compute_bayesian_rpi(games, remaining, teams, priors=None, n_sims=1000):
	"""Bayesian projected end-of-season RPI via Monte Carlo simulation.

	Args:
		games: completed games
		remaining: scheduled but unplayed games
		teams: list of team IDs
		priors: optional dict {team_id: prior_rpi} for seeded variant
		n_sims: number of simulations

	Returns dict of {team_id: {median, low, high}} (50th, 5th, 95th percentiles).
	"""
	if not remaining:
		return {}

	idx = {t: i for i, t in enumerate(teams)}
	n = len(teams)

	# Estimate team strengths from observed margins
	margins_by_team = defaultdict(list)
	for g in games:
		h = g["home_team_id"]
		a = g["away_team_id"]
		m = g["home_score"] - g["away_score"]
		margins_by_team[h].append(m)
		margins_by_team[a].append(-m)

	# Posterior parameters (conjugate normal)
	# Prior: N(mu_prior, sigma_prior^2)
	sigma_prior = 1.0
	sigma_obs = 4.0  # assumed observation noise (goal margin SD)

	strengths_mu = np.zeros(n)
	strengths_var = np.full(n, sigma_prior**2)

	for t in teams:
		i = idx[t]
		obs = margins_by_team.get(t, [])
		# Prior mean
		if priors and t in priors:
			mu0 = (priors[t] - 0.5) * 10  # scale RPI to strength space
		else:
			mu0 = 0.0

		if obs:
			obs_arr = np.array(obs)
			n_obs = len(obs_arr)
			obs_mean = obs_arr.mean()
			# Conjugate update
			prior_prec = 1.0 / (sigma_prior**2)
			obs_prec = n_obs / (sigma_obs**2)
			post_prec = prior_prec + obs_prec
			strengths_mu[i] = (prior_prec * mu0 + obs_prec * obs_mean) / post_prec
			strengths_var[i] = 1.0 / post_prec
		else:
			strengths_mu[i] = mu0
			# keep prior variance

	# Monte Carlo: sample strengths, simulate remaining, compute full-season RPI
	rng = np.random.default_rng(42)
	rpi_samples = {t: [] for t in teams}

	for _ in range(n_sims):
		# Sample strengths
		s = rng.normal(strengths_mu, np.sqrt(strengths_var))

		# Simulate remaining games
		sim_games = list(games)  # start with actual results
		for g in remaining:
			h = g["home_team_id"]
			a = g["away_team_id"]
			if h not in idx or a not in idx:
				continue
			diff = s[idx[h]] - s[idx[a]]
			# Logistic win probability
			p_home = 1.0 / (1.0 + np.exp(-0.4 * diff))
			if rng.random() < p_home:
				hs, as_ = 10, 7  # representative scores
			else:
				hs, as_ = 7, 10
			sim_games.append({
				"home_team_id": h,
				"away_team_id": a,
				"home_score": hs,
				"away_score": as_,
			})

		# Compute RPI on simulated full season
		sim_rpi = compute_rpi(sim_games, teams)
		for t in teams:
			rpi_samples[t].append(sim_rpi[t]["rpi"])

	result = {}
	for t in teams:
		arr = np.array(rpi_samples[t])
		result[t] = {
			"median": round(float(np.percentile(arr, 50)), 6),
			"low": round(float(np.percentile(arr, 5)), 6),
			"high": round(float(np.percentile(arr, 95)), 6),
		}
	return result


# ---------------------------------------------------------------------------
# Database writes
# ---------------------------------------------------------------------------

def upsert_rankings(cur, season_id, ranking_rows):
	"""Upsert into team_season_rankings."""
	sql = """
		INSERT INTO team_season_rankings (
			team_id, season_id, division_id, wins, losses,
			wp, owp, oowp, rpi,
			massey, massey_recency,
			projected_rpi_flat, projected_rpi_flat_low, projected_rpi_flat_high,
			projected_rpi_seeded, projected_rpi_seeded_low, projected_rpi_seeded_high,
			computed_at
		) VALUES (
			%(team_id)s, %(season_id)s, %(division_id)s, %(wins)s, %(losses)s,
			%(wp)s, %(owp)s, %(oowp)s, %(rpi)s,
			%(massey)s, %(massey_recency)s,
			%(projected_rpi_flat)s, %(projected_rpi_flat_low)s, %(projected_rpi_flat_high)s,
			%(projected_rpi_seeded)s, %(projected_rpi_seeded_low)s, %(projected_rpi_seeded_high)s,
			%(computed_at)s
		)
		ON CONFLICT (team_id, season_id) DO UPDATE SET
			division_id = EXCLUDED.division_id,
			wins = EXCLUDED.wins,
			losses = EXCLUDED.losses,
			wp = EXCLUDED.wp,
			owp = EXCLUDED.owp,
			oowp = EXCLUDED.oowp,
			rpi = EXCLUDED.rpi,
			massey = EXCLUDED.massey,
			massey_recency = EXCLUDED.massey_recency,
			projected_rpi_flat = EXCLUDED.projected_rpi_flat,
			projected_rpi_flat_low = EXCLUDED.projected_rpi_flat_low,
			projected_rpi_flat_high = EXCLUDED.projected_rpi_flat_high,
			projected_rpi_seeded = EXCLUDED.projected_rpi_seeded,
			projected_rpi_seeded_low = EXCLUDED.projected_rpi_seeded_low,
			projected_rpi_seeded_high = EXCLUDED.projected_rpi_seeded_high,
			computed_at = EXCLUDED.computed_at,
			updated_at = CURRENT_TIMESTAMP
	"""
	for row in ranking_rows:
		cur.execute(sql, row)


def upsert_history(cur, season_id, week_number, ranking_rows):
	"""Upsert into team_season_rankings_history."""
	sql = """
		INSERT INTO team_season_rankings_history (
			team_id, season_id, division_id, week_number,
			wins, losses,
			wp, owp, oowp, rpi,
			massey, massey_recency,
			projected_rpi_flat, projected_rpi_flat_low, projected_rpi_flat_high,
			projected_rpi_seeded, projected_rpi_seeded_low, projected_rpi_seeded_high,
			computed_at
		) VALUES (
			%(team_id)s, %(season_id)s, %(division_id)s, %(week_number)s,
			%(wins)s, %(losses)s,
			%(wp)s, %(owp)s, %(oowp)s, %(rpi)s,
			%(massey)s, %(massey_recency)s,
			%(projected_rpi_flat)s, %(projected_rpi_flat_low)s, %(projected_rpi_flat_high)s,
			%(projected_rpi_seeded)s, %(projected_rpi_seeded_low)s, %(projected_rpi_seeded_high)s,
			%(computed_at)s
		)
		ON CONFLICT (team_id, season_id, week_number) DO UPDATE SET
			division_id = EXCLUDED.division_id,
			wins = EXCLUDED.wins,
			losses = EXCLUDED.losses,
			wp = EXCLUDED.wp,
			owp = EXCLUDED.owp,
			oowp = EXCLUDED.oowp,
			rpi = EXCLUDED.rpi,
			massey = EXCLUDED.massey,
			massey_recency = EXCLUDED.massey_recency,
			projected_rpi_flat = EXCLUDED.projected_rpi_flat,
			projected_rpi_flat_low = EXCLUDED.projected_rpi_flat_low,
			projected_rpi_flat_high = EXCLUDED.projected_rpi_flat_high,
			projected_rpi_seeded = EXCLUDED.projected_rpi_seeded,
			projected_rpi_seeded_low = EXCLUDED.projected_rpi_seeded_low,
			projected_rpi_seeded_high = EXCLUDED.projected_rpi_seeded_high,
			computed_at = EXCLUDED.computed_at
	"""
	for row in ranking_rows:
		row_with_week = {**row, "week_number": week_number}
		cur.execute(sql, row_with_week)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_native(val):
	"""Convert numpy types to Python natives for psycopg2 compatibility."""
	if val is None:
		return None
	if isinstance(val, (np.integer,)):
		return int(val)
	if isinstance(val, (np.floating,)):
		return float(val)
	return val


def native_row(row):
	"""Convert all values in a dict to Python native types."""
	return {k: to_native(v) for k, v in row.items()}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def compute_all_rankings(games, remaining, teams, season_start, priors=None):
	"""Run all 5 ranking systems. Returns list of row dicts."""
	if not games:
		return []

	rpi = compute_rpi(games, teams)
	massey = compute_massey(games, teams)
	massey_rec = compute_massey_recency(games, teams, season_start)
	proj_flat = compute_bayesian_rpi(games, remaining, teams, priors=None)
	proj_seeded = compute_bayesian_rpi(games, remaining, teams, priors=priors) if priors else {}

	# Build division_id lookup from games
	div_by_team = {}
	for g in games:
		div_by_team[g["home_team_id"]] = g.get("division_id", 1)
		div_by_team[g["away_team_id"]] = g.get("division_id", 1)

	now = datetime.utcnow()
	rows = []
	for t in teams:
		r = rpi.get(t, {})
		pf = proj_flat.get(t, {})
		ps = proj_seeded.get(t, {})
		rows.append(native_row({
			"team_id": t,
			"season_id": None,  # filled by caller
			"division_id": div_by_team.get(t, 1),
			"wins": r.get("wins", 0),
			"losses": r.get("losses", 0),
			"wp": r.get("wp"),
			"owp": r.get("owp"),
			"oowp": r.get("oowp"),
			"rpi": r.get("rpi"),
			"massey": massey.get(t),
			"massey_recency": massey_rec.get(t),
			"projected_rpi_flat": pf.get("median"),
			"projected_rpi_flat_low": pf.get("low"),
			"projected_rpi_flat_high": pf.get("high"),
			"projected_rpi_seeded": ps.get("median"),
			"projected_rpi_seeded_low": ps.get("low"),
			"projected_rpi_seeded_high": ps.get("high"),
			"computed_at": now,
		}))
	return rows


def print_summary(rows, team_names):
	"""Print a summary table to stdout."""
	# Sort by RPI descending
	sorted_rows = sorted(rows, key=lambda r: r.get("rpi") or 0, reverse=True)
	print(f"\n{'Rank':<5} {'Team':<25} {'W-L':<8} {'RPI':<8} {'Massey':<9} {'MasseyR':<9} {'ProjRPI':<8}")
	print("-" * 80)
	for i, r in enumerate(sorted_rows[:30], 1):
		name = team_names.get(r["team_id"], r["team_id"])[:24]
		wl = f"{r['wins']}-{r['losses']}"
		rpi = f"{r['rpi']:.4f}" if r["rpi"] is not None else "N/A"
		mas = f"{r['massey']:+.3f}" if r["massey"] is not None else "N/A"
		masr = f"{r['massey_recency']:+.3f}" if r["massey_recency"] is not None else "N/A"
		proj = f"{r['projected_rpi_flat']:.4f}" if r.get("projected_rpi_flat") is not None else "N/A"
		print(f"{i:<5} {name:<25} {wl:<8} {rpi:<8} {mas:<9} {masr:<9} {proj:<8}")
	if len(sorted_rows) > 30:
		print(f"  ... and {len(sorted_rows) - 30} more teams")


def main():
	parser = argparse.ArgumentParser(description="Compute team rankings")
	parser.add_argument("--season", help="Season ID (default: current)")
	parser.add_argument("--backfill", action="store_true", help="Recompute all weeks historically")
	parser.add_argument("--dry-run", action="store_true", help="Print rankings without writing")
	args = parser.parse_args()

	conn = get_connection()
	try:
		with conn.cursor() as cur:
			season_id, start_date = load_season_info(cur, args.season)
			print(f"Season: {season_id} (start: {start_date})")

			all_games = load_games(cur, season_id)
			remaining = load_remaining_games(cur, season_id)
			team_names = load_team_names(cur)
			priors = load_prior_rankings(cur, season_id)

			if not all_games:
				print("No completed games found. Nothing to compute.")
				return

			teams = build_team_set(all_games)
			week1 = get_week1_monday(start_date)
			current_week = get_current_week(week1)

			# For completed seasons (no remaining games), cap at last game week
			if not remaining and all_games:
				last_game_date = max(g["game_date"] for g in all_games)
				last_game_week = max(1, (last_game_date - week1).days // 7 + 1)
				current_week = min(current_week, last_game_week)

			print(f"Games: {len(all_games)} final, {len(remaining)} remaining")
			print(f"Teams: {len(teams)}, Week 1: {week1}, Current week: {current_week}")
			if priors:
				print(f"Prior season rankings: {len(priors)} teams")

			if args.backfill:
				print(f"\nBackfilling weeks 1 through {current_week}...")
				for week in range(1, current_week + 1):
					week_games = filter_games_through_week(all_games, week1, week)
					if not week_games:
						print(f"  Week {week}: 0 games, skipping")
						continue

					week_teams = build_team_set(week_games)
					# Remaining = all games not yet played as of this week
					week_cutoff = week1 + timedelta(days=7 * week)
					week_remaining = [
						g for g in all_games if g["game_date"] >= week_cutoff
					] + remaining

					rows = compute_all_rankings(
						week_games, week_remaining, week_teams, start_date, priors
					)
					for r in rows:
						r["season_id"] = season_id

					if not args.dry_run:
						upsert_history(cur, season_id, week, rows)
						conn.commit()
						# Final week also updates current rankings
						if week == current_week:
							upsert_rankings(cur, season_id, rows)
							conn.commit()

					print(f"  Week {week}: {len(week_games)} games, {len(week_teams)} teams")

				# Print final week summary
				if rows:
					print_summary(rows, team_names)
			else:
				# Single computation for current state
				rows = compute_all_rankings(
					all_games, remaining, teams, start_date, priors
				)
				for r in rows:
					r["season_id"] = season_id

				print_summary(rows, team_names)

				if not args.dry_run:
					upsert_rankings(cur, season_id, rows)
					if current_week > 0:
						upsert_history(cur, season_id, current_week, rows)
					conn.commit()
					print(f"\nWrote {len(rows)} rankings to database (week {current_week})")
				else:
					print("\nDry run — no database writes.")

	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()


if __name__ == "__main__":
	main()
