# Team Rankings

Five ranking systems computed weekly by `scripts/rankings/compute_rankings.py`. Results stored in `team_season_rankings` (latest snapshot) and `team_season_rankings_history` (weekly snapshots).

## RPI (Rating Percentage Index)

Standard NCAA formula. Combines a team's winning percentage with the strength of its schedule.

```
RPI = 0.25 * WP + 0.50 * OWP + 0.25 * OOWP
```

- **WP** (Winning Percentage): wins / (wins + losses)
- **OWP** (Opponents' Winning Percentage): mean WP of opponents, excluding head-to-head games against the team being ranked
- **OOWP** (Opponents' Opponents' Winning Percentage): mean OWP of opponents

The heavy OWP weighting (50%) rewards teams that play tough schedules. A team that goes 10-5 against strong opponents can rank higher than a team that goes 15-0 against weak ones.

## Massey Ranking

Least-squares regression on score margins. Each game produces an equation: `r_home - r_away = margin`, clamped to [-8, 8] to limit blowout influence. The system solves for team strengths that best explain observed margins, with a sum-to-zero constraint so rankings center around 0.

Positive rankings indicate above-average teams. The magnitude reflects expected margin of victory against an average (0-ranked) team.

Falls back to `lstsq` if the normal equations are singular (rare, requires disconnected schedule components).

## Massey Recency-Weighted

Same as Massey but applies exponential decay to older games:

```
w_k = exp(-0.02 * (t_max - t_k))
```

where `t_k` is days since season start and `t_max` is the most recent game day. Recent games have weight ~1.0; a game from 50 days ago has weight ~0.37. This captures teams that are improving or declining over the season.

## Bayesian Projected RPI (Flat Prior)

Monte Carlo simulation of end-of-season RPI. Estimates team strengths from observed score margins using a conjugate normal model, then simulates remaining scheduled games 1,000 times.

- **Strength estimation**: Each team gets a posterior N(mu, sigma^2) from a flat N(0, 1) prior updated with observed margins (assumed sigma_obs = 4 goals)
- **Game simulation**: For each remaining game, a logistic function converts the strength difference to a win probability. A winner is sampled and given representative scores (10-7 or 7-10)
- **RPI computation**: Full-season RPI is computed for each simulation

Reports the 50th percentile (median projected RPI) and 5th/95th percentile confidence interval.

Only populated when remaining scheduled games exist. NULL for completed seasons.

## Bayesian Projected RPI (Seeded)

Same simulation method but seeds the prior with the team's RPI from the previous season. Prior season RPI is scaled to strength space: `mu_prior = (rpi - 0.5) * 10`. This pulls early-season projections toward historical performance, which is useful when few games have been played.

As more current-season games accumulate, the prior's influence diminishes and the seeded and flat projections converge.

## Database Schema

### `team_season_rankings`

Current rankings snapshot. One row per team per season. Upserted on `(team_id, season_id)`.

| Column | Description |
|--------|-------------|
| `wp`, `owp`, `oowp`, `rpi` | RPI components |
| `massey` | Massey ranking |
| `massey_recency` | Recency-weighted Massey |
| `projected_rpi_flat` | Projected RPI median (flat prior) |
| `projected_rpi_flat_low`, `_high` | 5th/95th percentile |
| `projected_rpi_seeded` | Projected RPI median (seeded prior) |
| `projected_rpi_seeded_low`, `_high` | 5th/95th percentile |
| `wins`, `losses`, `division_id` | Context |
| `computed_at` | Timestamp of computation |

### `team_season_rankings_history`

Weekly snapshots for trend analysis. Same columns plus `week_number`. Upserted on `(team_id, season_id, week_number)`.

Week 1 starts on the first Monday on or after the season's `start_date`. Each week is 7 days.

## Usage

```bash
# Current season
python -m scripts.rankings.compute_rankings

# Specific season
python -m scripts.rankings.compute_rankings --season 2025

# Backfill all weeks for a season
python -m scripts.rankings.compute_rankings --season 2025 --backfill

# Preview without writing
python -m scripts.rankings.compute_rankings --dry-run
```

Runs weekly via GitHub Actions (Monday 8:00 UTC / midnight PT). Manual dispatch available with optional season and backfill inputs.
