# sleepless

Keeps a Linux laptop/box awake 24/7, lid open or closed — a `caffeinate`
equivalent plus a persistent mode.

- `bin/sleepless` — on-demand blocker: `sleepless` (until Ctrl+C) or
  `sleepless <cmd>` (while the command runs). Uses
  `systemd-inhibit --what=sleep:idle:shutdown:handle-lid-switch`.
- `systemd/sleepless.conf` — logind drop-in ignoring lid switch, suspend /
  hibernate keys and idle, on AC, battery and docked.
- `install.sh` enables the persistent mode and aligns the Cinnamon/GNOME
  lid-close keys. `install.sh --off` restores suspend defaults.
