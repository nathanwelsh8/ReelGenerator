#!/usr/bin/env bash
set -euo pipefail

# Ensure ImageMagick policy is patched at container start (idempotent)
/usr/local/bin/patch_imagemagick_policy.sh || true

# Ensure working directory
cd /app

# Ensure cron job exists (idempotent)
PY=$(command -v python3 || echo /usr/local/bin/python3)
CRON_FILE=/etc/cron.d/app-cron
if [ ! -f "$CRON_FILE" ]; then
	echo "Creating $CRON_FILE"
	{
		echo 'SHELL=/bin/bash'
		echo 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
		echo ''
	echo "0 * * * * root echo \"[CRON] $(date '+%Y-%m-%d %H:%M:%S') Running main.py\" >> /var/log/cron.log; cd /app && $PY /app/main.py >> /var/log/cron.log 2>&1"
	echo "0 */2 * * * root echo \"[CRON] $(date '+%Y-%m-%d %H:%M:%S') Running upload_to_instagram.py\" >> /var/log/cron.log; cd /app && $PY /app/upload_to_instagram.py >> /var/log/cron.log 2>&1"
	} > "$CRON_FILE"
	chmod 0644 "$CRON_FILE"
fi

# Make sure the log file exists
touch /var/log/cron.log || true

# Print crontab for debugging
crontab -l || true

# Start cron in the foreground so container stays alive
exec cron -f
