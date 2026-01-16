#!/bin/bash
# Setup script for lacrosse-stats daily sync cron job
#
# This installs a launchd job to run the daily sync at midnight local time.
#
# Usage:
#   ./scripts/cron/setup_cron.sh install    # Install and start the job
#   ./scripts/cron/setup_cron.sh uninstall  # Stop and remove the job
#   ./scripts/cron/setup_cron.sh status     # Check job status
#   ./scripts/cron/setup_cron.sh run        # Run sync manually

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST_NAME="com.lacrosse-stats.daily-sync.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

case "$1" in
    install)
        echo "Installing daily sync cron job..."

        # Create log directory
        mkdir -p "$PROJECT_DIR/outputs/logs"

        # Copy plist to LaunchAgents
        cp "$PLIST_SRC" "$PLIST_DST"
        echo "Copied plist to $PLIST_DST"

        # Load the job
        launchctl load "$PLIST_DST"
        echo "Loaded launchd job"

        echo ""
        echo "Daily sync installed. Will run at midnight local time."
        echo "Logs: $PROJECT_DIR/outputs/logs/daily-sync.log"
        echo ""
        echo "To test now: $0 run"
        ;;

    uninstall)
        echo "Uninstalling daily sync cron job..."

        if [ -f "$PLIST_DST" ]; then
            launchctl unload "$PLIST_DST" 2>/dev/null || true
            rm "$PLIST_DST"
            echo "Removed launchd job"
        else
            echo "Job not installed"
        fi
        ;;

    status)
        echo "Checking daily sync status..."
        if launchctl list | grep -q "com.lacrosse-stats.daily-sync"; then
            echo "Status: INSTALLED and ACTIVE"
            launchctl list | grep "com.lacrosse-stats.daily-sync"
        else
            echo "Status: NOT INSTALLED"
        fi

        echo ""
        echo "Recent logs:"
        if [ -f "$PROJECT_DIR/outputs/logs/daily-sync.log" ]; then
            tail -20 "$PROJECT_DIR/outputs/logs/daily-sync.log"
        else
            echo "No logs yet"
        fi
        ;;

    run)
        echo "Running daily sync manually..."
        cd "$PROJECT_DIR"
        source .venv/bin/activate
        python scripts/sync_daily.py --season 2026
        ;;

    *)
        echo "Usage: $0 {install|uninstall|status|run}"
        echo ""
        echo "Commands:"
        echo "  install    Install and start the daily sync job"
        echo "  uninstall  Stop and remove the job"
        echo "  status     Check if job is running and show recent logs"
        echo "  run        Run the sync manually (for testing)"
        exit 1
        ;;
esac
