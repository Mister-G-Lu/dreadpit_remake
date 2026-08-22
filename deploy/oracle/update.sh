#!/usr/bin/env bash
# Pull latest Kiln code, rebuild, restart the service.
#   sudo bash /opt/dreadpit_remake/deploy/oracle/update.sh
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

INSTALL_DIR="${INSTALL_DIR:-/opt/dreadpit_remake}"
cd "$INSTALL_DIR"
echo "Pulling ${REPO_BRANCH:-main}..."
git fetch --prune origin
git pull --ff-only origin "${REPO_BRANCH:-main}"

cd "$INSTALL_DIR/kiln"
chown -R kiln:kiln "$INSTALL_DIR" 2>/dev/null || true

echo "Installing dependencies..."
sudo -u kiln bash -lc "cd '$INSTALL_DIR/kiln' && npm ci --no-audit --no-fund"
echo "Building client..."
sudo -u kiln bash -lc "cd '$INSTALL_DIR/kiln' && npm run build"

echo "Restarting kiln.service..."
systemctl daemon-reload
systemctl restart kiln.service
systemctl status kiln.service --no-pager -l || true
