#!/bin/bash
# rig-panel package: native GTK4/libadwaita control panel for this machine's
# dev tools + sleepless power + Tailscale, with a text CLI for SSH.
# Needs: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gnome-terminal.
# (zenity is only a fallback for the old menu UI.)
set -u
PKG="$(cd "$(dirname "$0")" && pwd)"

missing=""
for dep in python3 gnome-terminal; do
  command -v "$dep" >/dev/null || missing="$missing $dep"
done
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null \
  || missing="$missing python3-gi/gir1.2-gtk-4.0/gir1.2-adw-1"
if [ -n "$missing" ]; then
  echo "missing:$missing"
  echo "install with: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gnome-terminal"
  exit 1
fi

install -Dm755 "$PKG/bin/rig-panel" "$HOME/.local/bin/rig-panel"
install -Dm755 "$PKG/gui/rig-panel-gui" "$HOME/.local/bin/rig-panel-gui"

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
