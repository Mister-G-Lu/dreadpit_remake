#!/usr/bin/env bash
# Kiln - Oracle Cloud Always Free (ARM) provisioning
#
# Run on a fresh Ubuntu 22.04/24.04 or Oracle Linux 8/9 VM as root (or with sudo):
#   sudo bash setup.sh
#
# Idempotent-ish: it refuses to overwrite /etc/kiln.env and an existing
# /opt/dreadpit_remake, and can be re-run after you fill in the env file.
set -euo pipefail

# --- config ---------------------------------------------------------------
REPO_URL="${REPO_URL:-https://github.com/Mister-G-Lu/dreadpit_remake.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/dreadpit_remake}"
KILN_USER="kiln"
CADDY_USER="caddy"
# Tested Node version; bump to the latest 22.x LTS if you prefer.
NODE_VERSION="${NODE_VERSION:-22.22.3}"

log()  { printf '\033[1;34m[kiln]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[kiln]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[kiln] %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root (sudo bash setup.sh)"

# --- arch / distro ---------------------------------------------------------
ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64) NODE_TARGET="arm64" ;;
  x86_64|amd64)  NODE_TARGET="x64"   ;;
  *) die "Unsupported arch: $ARCH" ;;
esac

if command -v apt-get >/dev/null 2>&1; then
  PKG=apt
elif command -v dnf >/dev/null 2>&1; then
  PKG=dnf
else
  die "Need apt (Debian/Ubuntu) or dnf (Oracle/RHEL-family)"
fi

# --- Node 22 ---------------------------------------------------------------
node_ok=0
if command -v node >/dev/null 2>&1; then
  v="$(node -v | sed 's/^v//')"
  maj="${v%%.*}"
  if [[ "$maj" -ge 22 ]]; then node_ok=1; fi
fi

if [[ "$node_ok" -eq 0 ]]; then
  log "Installing Node $NODE_VERSION (${NODE_TARGET}) from nodejs.org"
  case "$PKG" in
    apt) apt-get update -y && apt-get install -y curl ca-certificates tar gzip git ;;
    dnf) dnf install -y curl ca-certificates tar gzip git ;;
  esac
  tmp="$(mktemp -d)"
  tarball="node-v${NODE_VERSION}-linux-${NODE_TARGET}.tar.gz"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/${tarball}" -o "${tmp}/${tarball}"
  tar -xzf "${tmp}/${tarball}" -C /usr/local --strip-components=1
  rm -rf "$tmp"
else
  log "Node $(node -v) already present"
fi

command -v node || die "node not found in /usr/local/bin - is /usr/local/bin on PATH?"
node -v && npm -v

# --- system users ----------------------------------------------------------
nologin="/usr/sbin/nologin"
[[ -e "$nologin" ]] || nologin="/sbin/nologin"
[[ -e "$nologin" ]] || nologin="/bin/false"

if ! id -u "$KILN_USER" >/dev/null 2>&1; then
  useradd -r -m -d "/var/lib/${KILN_USER}" -s "$nologin" "$KILN_USER"
fi
if ! id -u "$CADDY_USER" >/dev/null 2>&1; then
  useradd -r -m -d "/var/lib/${CADDY_USER}" -s "$nologin" "$CADDY_USER"
fi

# --- app code ---------------------------------------------------------------
if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "$INSTALL_DIR already exists - leaving it (use update.sh to pull)"
else
  log "Cloning ${REPO_URL} (branch ${REPO_BRANCH}) to ${INSTALL_DIR}"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

chown -R "$KILN_USER:$KILN_USER" "$INSTALL_DIR"

cd "$INSTALL_DIR/kiln"
log "npm ci (dependencies)"
sudo -u "$KILN_USER" bash -lc 'cd "$1/kiln" && npm ci --no-audit --no-fund' _ "$INSTALL_DIR"
log "npm run build (Vite client -> kiln/dist)"
sudo -u "$KILN_USER" bash -lc 'cd "$1/kiln" && npm run build' _ "$INSTALL_DIR"

# --- env -------------------------------------------------------------------
ENV_FILE=/etc/kiln.env
if [[ -e "$ENV_FILE" ]]; then
  warn "$ENV_FILE already exists - not overwriting. Edit it to set GEMINI_API_KEY."
else
  cp "$INSTALL_DIR/deploy/oracle/kiln.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  log "Wrote $ENV_FILE from template"
  warn "Edit $ENV_FILE now to set GEMINI_API_KEY and (optionally) FIRE_UTC_HOUR=12."
fi

# --- Caddy ----------------------------------------------------------------
if ! command -v caddy >/dev/null 2>&1; then
  log "Installing Caddy binary (linux/${NODE_TARGET})"
  case "$ARCH" in aarch64|arm64) C_ARCH="arm64" ;; *) C_ARCH="amd64" ;; esac
  curl -fsSL "https://caddyserver.com/api/download?os=linux&arch=${C_ARCH}" -o /usr/local/bin/caddy
  chmod 0755 /usr/local/bin/caddy
fi
mkdir -p /etc/caddy /var/lib/caddy
cp "$INSTALL_DIR/deploy/oracle/Caddyfile.template" /etc/caddy/Caddyfile
chown -R "$CADDY_USER:$CADDY_USER" /var/lib/caddy

# --- systemd --------------------------------------------------------------
cp "$INSTALL_DIR/deploy/oracle/kiln.service"   /etc/systemd/system/kiln.service
cp "$INSTALL_DIR/deploy/oracle/caddy.service"  /etc/systemd/system/caddy.service
cp "$INSTALL_DIR/deploy/oracle/kiln-round.service" /etc/systemd/system/kiln-round.service
cp "$INSTALL_DIR/deploy/oracle/kiln-round.timer"   /etc/systemd/system/kiln-round.timer

systemctl daemon-reload
systemctl enable kiln.service
systemctl restart kiln.service

# Note: the poller (KILN_POLL=1 default) is the one trigger; the round timer is
# left disabled so two processes can't race the same round.
systemctl disable kiln-round.timer >/dev/null 2>&1 || true

# Caddy is installed but left stopped until you set a domain in Caddyfile.
systemctl enable caddy.service >/dev/null 2>&1 || true

# --- summary --------------------------------------------------------------
IP="$(curl -4 -fsSL --max-time 5 https://ifconfig.me/ip 2>/dev/null || true)"

log "Done."
echo
echo "Next steps:"
echo "  1. sudo nano /etc/kiln.env        -> set GEMINI_API_KEY (and FIRE_UTC_HOUR=12)"
echo "  2. sudo systemctl restart kiln"
echo "  3. curl -s http://127.0.0.1:3000/api/health"
echo "  4. In OCI console Security List / NSG, allow inbound TCP 80 and 443"
echo "     (22 should already be allowed)."
echo "  5. For HTTPS, point a DNS A record at this VM, edit /etc/caddy/Caddyfile"
echo "     to use the {$DOMAIN} block, then: sudo systemctl enable --now caddy"
echo
echo "  Public IP (from ifconfig.me): ${IP:-<your VM public IP>}"
echo "  Logs: sudo journalctl -u kiln -f"
