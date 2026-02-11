#!/bin/bash
# Setup cron job for database pinging

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"
PING_SCRIPT="$PROJECT_DIR/scripts/utils/ping_database.py"
PYTHON_PATH=$(which python3)

# Create a temporary file with the new cron job
TEMP_CRON=$(mktemp)

# Export existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Check if ping job already exists
if grep -q "ping_database.py" "$TEMP_CRON"; then
	echo "Cron job already exists. Removing old entries..."
	grep -v "ping_database.py" "$TEMP_CRON" > "$TEMP_CRON.tmp"
	mv "$TEMP_CRON.tmp" "$TEMP_CRON"
fi

# Add new cron jobs (Tuesday 10am and Friday 2pm)
echo "" >> "$TEMP_CRON"
echo "# Database ping to keep Supabase free tier active (2x per week)" >> "$TEMP_CRON"
echo "0 10 * * 2 cd $PROJECT_DIR && $PYTHON_PATH $PING_SCRIPT >> $PROJECT_DIR/outputs/logs/db_ping.log 2>&1" >> "$TEMP_CRON"
echo "0 14 * * 5 cd $PROJECT_DIR && $PYTHON_PATH $PING_SCRIPT >> $PROJECT_DIR/outputs/logs/db_ping.log 2>&1" >> "$TEMP_CRON"

# Install the new crontab
crontab "$TEMP_CRON"

# Clean up
rm "$TEMP_CRON"

echo "Cron job installed successfully"
echo "Database will be pinged:"
echo "  - Tuesday at 10:00 AM"
echo "  - Friday at 2:00 PM"
echo ""
echo "Logs will be written to: $PROJECT_DIR/outputs/logs/db_ping.log"
echo ""
echo "To verify: crontab -l"
echo "To remove: crontab -e (then delete the ping_database.py lines)"
