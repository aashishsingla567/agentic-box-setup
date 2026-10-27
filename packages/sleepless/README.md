# sleepless

An on-demand `systemd-inhibit` wrapper and an explicitly selected persistent power policy.

```bash
./install.sh --only sleepless.cli --apply
sleepless                 # until Ctrl+C
sleepless your-command    # while a command runs
./install.sh --only sleepless.power --set sleepless.mode=always-on --apply
```

Default setup installs the CLI only and preserves power policy. `always-on` installs the logind drop-in and aligns supported Cinnamon/GNOME keys to keep the machine awake. Logind is not restarted during setup; its drop-in takes effect on the next restart/boot, preserving active login sessions. `normal` removes this package's logind drop-in; desktop gsettings previously set by always-on must be reviewed separately in the desktop power settings. `unchanged` performs no power-policy action.

Direct `packages/sleepless/install.sh` defaults to install-only; `--on` and `--off` are explicit power options. Configure remote access/startup before relying on lid-closed use.
