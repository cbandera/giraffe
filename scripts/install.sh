#!/usr/bin/env bash
# Development install for the current user (no root).
# Usage: scripts/install.sh [--no-shortcut]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="io.github.giraffe.Giraffe"
BIN="$HOME/.local/bin/giraffe"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"

if [ ! -x "$REPO/.venv/bin/python" ]; then
  python3 -m venv --system-site-packages "$REPO/.venv"
fi
"$REPO/.venv/bin/pip" install -q -e "$REPO"

mkdir -p "$(dirname "$BIN")" "$APPS" "$ICONS"
cat > "$BIN" <<LAUNCHER
#!/bin/sh
exec "$REPO/.venv/bin/python" -m giraffe "\$@"
LAUNCHER
chmod +x "$BIN"

sed "s|^Exec=giraffe|Exec=$BIN|" "$REPO/data/$APP_ID.desktop" > "$APPS/$APP_ID.desktop"
cp "$REPO/data/icons/$APP_ID.svg" "$ICONS/$APP_ID.svg"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" || true

if [ "${1:-}" != "--no-shortcut" ]; then
  /usr/bin/python3 "$REPO/scripts/register_shortcut.py" "$BIN --clipboard" "<Ctrl><Alt>g"
fi
echo "Installed. Run: giraffe invoice.pdf"
