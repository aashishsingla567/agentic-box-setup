#!/bin/bash
# sleepless package: `sleepless` on-demand inhibitor + persistent 24/7 mode.
#   ./install.sh          install binary, enable 24/7 lid-closed mode
#   ./install.sh --off    install binary, keep default suspend behavior
set -u
PKG="$(cd "$(dirname "$0")" && pwd)"

install -Dm755 "$PKG/bin/sleepless" "$HOME/.local/bin/sleepless"
echo "installed ~/.local/bin/sleepless"

MODE="${1:---on}"
if [ "$MODE" = "--off" ]; then
  sudo rm -f /etc/systemd/logind.conf.d/sleepless.conf
  sudo systemctl restart systemd-logind
  echo "24/7 mode OFF (system defaults)"
else
  sudo mkdir -p /etc/systemd/logind.conf.d
  sudo install -Dm644 "$PKG/systemd/sleepless.conf" /etc/systemd/logind.conf.d/sleepless.conf
  sudo systemctl restart systemd-logind
  # Desktop layer (Cinnamon + GNOME keys) so the DE agrees with logind.
  gsettings set org.cinnamon.settings-daemon.plugins.power lid-close-ac-action 'nothing' 2>/dev/null || true
  gsettings set org.cinnamon.settings-daemon.plugins.power lid-close-battery-action 'nothing' 2>/dev/null || true
  gsettings set org.gnome.settings-daemon.plugins.power lid-close-ac-action 'nothing' 2>/dev/null || true
  gsettings set org.gnome.settings-daemon.plugins.power lid-close-battery-action 'nothing' 2>/dev/null || true
  gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' 2>/dev/null || true
  gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing' 2>/dev/null || true
  echo "24/7 mode ON — safe to close the lid"
fi
