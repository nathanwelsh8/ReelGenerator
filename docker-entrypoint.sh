#!/usr/bin/env bash
set -euo pipefail

# Ensure ImageMagick policy is patched at container start (idempotent)
/usr/local/bin/patch_imagemagick_policy.sh || true

# Ensure working directory
cd /app

# Always (re)write cron job file to avoid stale configs from image build
PY=$(command -v python3 || echo /usr/local/bin/python3)
CRON_FILE=/etc/cron.d/app-cron
echo "Writing $CRON_FILE"
cat > "$CRON_FILE" <<'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Run upload_to_instagram.py every 2 hours
0 */2 * * * root echo "[CRON] $(date '+%Y-%m-%d %H:%M:%S') Running upload_to_instagram.py" >> /var/log/cron.log; cd /app && /usr/local/bin/python3 /app/upload_to_instagram.py >> /var/log/cron.log 2>&1
EOF
chmod 0644 "$CRON_FILE"

# Optionally append a 1-minute heartbeat when enabled via env
if [ "${CRON_DEBUG_HEARTBEAT:-}" = "1" ]; then
	echo "* * * * * root echo \"[CRON] $(date '+%Y-%m-%d %H:%M:%S') heartbeat\" >> /var/log/cron.log" >> "$CRON_FILE"
	chmod 0644 "$CRON_FILE"
fi

# Make sure the log file exists
touch /var/log/cron.log || true

# Show cron.d file for debugging
echo "--- $CRON_FILE ---"
sed -n '1,200p' "$CRON_FILE" || true

# Start cron in the foreground so container stays alive
exec cron -f
