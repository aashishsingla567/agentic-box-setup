# rig-panel

Native GTK4/libadwaita control panel for the agentic box: tool versions,
sleepless power mode, updates (opencode, Codex, Claude, Cursor, T3, agy)
and Tailscale — plus a `rig-panel --status` text mode for SSH.

- `gui/rig-panel-gui` — the app. Sidebar navigation, labeled rows and
  switches, state always in words (never color alone), toasts + modal
  error dialogs, `RIG_PANEL_SELFTEST=1` headless UI smoke test.
- `bin/rig-panel` — CLI (`--status`, `--on`, `--off`); launches the app
  when a display is present, zenity menu fallback otherwise.

Needs `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `gnome-terminal`.
