# Base prerequisites

`base.packages` installs Debian-family apt prerequisites. When startup is selected in the configuration package list it also includes SSH/systemd-session prerequisites and the x86_64 eCryptfs helper unless mounted policy is selected. Rig Panel adds GTK dependencies. Individual `--only` scopes require their prerequisites already installed; they do not silently add unrelated packages.

`base.node` resolves an official Node major line or exact version, verifies the upstream archive SHA-256, stages extraction and installs under `~/.local/share/agentic-box/node`. An atomic `current` symlink selects the managed version. Existing system Node installations remain available. It adds one idempotent PATH hook to `.profile` and `.zprofile`; symlinked profiles are preserved and need the hook added manually. Open a new login shell, or source `~/.config/agentic-box/env.sh`.
