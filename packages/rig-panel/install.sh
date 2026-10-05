#!/bin/bash
# rig-panel package: zenity GUI control panel for this machine's
# dev tools + sleepless power + Tailscale. Needs: zenity, gnome-terminal.
set -u
PKG="$(cd "$(dirname "$0")" && pwd)"

command -v zenity >/dev/null || { echo "install zenity first (sudo apt install zenity)"; exit 1; }

install -Dm755 "$PKG/bin/rig-panel" "$HOME/.local/bin/rig-panel"

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"
cp "$PKG/icons/rig-panel.svg" "$ICON_DIR/rig-panel.svg"

APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"
# Point Icon at the installed absolute path (robust without an icon cache).
sed "s|^Icon=.*|Icon=$ICON_DIR/rig-panel.svg|" "$PKG/desktop/rig-panel.desktop" > "$APP_DIR/rig-panel.desktop"
chmod +x "$APP_DIR/rig-panel.desktop"
update-desktop-database "$APP_DIR" 2>/dev/null || true

echo "rig-panel installed — find 'Rig Panel' in Settings, or run: rig-panel"
