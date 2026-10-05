#!/bin/bash
# Google Antigravity: CLI (agy) + desktop app + IDE, system-wide in /opt.
# Bump the VERSION/HASH vars when new releases land (see
# https://antigravity.google/download/).
set -u
. "$(dirname "$0")/common.sh"

echo "--- agy CLI ---"
fetch_to_file https://antigravity.google/cli/install.sh /tmp/agentic-agy-install.sh
bash /tmp/agentic-agy-install.sh
rm -f /tmp/agentic-agy-install.sh
agy --version

APP_VERSION="${ANTIGRAVITY_APP_VERSION:-2.19.1}"
APP_BUILD="${ANTIGRAVITY_APP_BUILD:-6046815158665216}"
IDE_VERSION="${ANTIGRAVITY_IDE_VERSION:-2.5.5}"
IDE_BUILD="${ANTIGRAVITY_IDE_BUILD:-4923483625488384}"

echo "--- Antigravity app $APP_VERSION ---"
fetch_to_file \
  "https://storage.googleapis.com/antigravity-public/antigravity-hub/${APP_VERSION}-${APP_BUILD}/linux-x64/Antigravity.tar.gz" \
  /tmp/agentic-antigravity.tar.gz
sudo mkdir -p /opt/antigravity
sudo tar -xzf /tmp/agentic-antigravity.tar.gz -C /opt/antigravity --strip-components=1
rm -f /tmp/agentic-antigravity.tar.gz

echo "--- Antigravity IDE $IDE_VERSION ---"
mkdir -p /tmp/agentic-ide-staging
fetch_to_file \
  "https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/${IDE_VERSION}-${IDE_BUILD}/linux-x64/Antigravity%20IDE.tar.gz" \
  "/tmp/agentic-ide.tar.gz"
tar -xzf "/tmp/agentic-ide.tar.gz" -C /tmp/agentic-ide-staging
sudo mkdir -p /opt/antigravity-ide
sudo cp -a "/tmp/agentic-ide-staging/Antigravity IDE/." /opt/antigravity-ide/
rm -rf /tmp/agentic-ide-staging "/tmp/agentic-ide.tar.gz"

# Electron sandbox bit + launchers + menu entries (quoted paths survive spaces)
sudo chown root:root /opt/antigravity/chrome-sandbox /opt/antigravity-ide/chrome-sandbox
sudo chmod 4755 /opt/antigravity/chrome-sandbox /opt/antigravity-ide/chrome-sandbox
sudo tee /usr/local/bin/antigravity >/dev/null <<'EOF'
#!/bin/sh
exec /opt/antigravity/antigravity "$@" --ozone-platform=x11
EOF
sudo tee /usr/local/bin/antigravity-ide >/dev/null <<'EOF'
#!/bin/sh
exec /opt/antigravity-ide/antigravity-ide "$@" --ozone-platform=x11
EOF
sudo chmod +x /usr/local/bin/antigravity /usr/local/bin/antigravity-ide
sudo mkdir -p /usr/share/icons/hicolor/512x512/apps
sudo cp /opt/antigravity-ide/resources/app/resources/linux/code.png \
  /usr/share/icons/hicolor/512x512/apps/antigravity-ide.png
sudo tee /usr/share/applications/antigravity.desktop >/dev/null <<'EOF'
[Desktop Entry]
Name=Antigravity
Comment=Google Antigravity - agent-first development
Exec=/usr/local/bin/antigravity %U
Icon=/usr/share/icons/hicolor/512x512/apps/antigravity-ide.png
Terminal=false
Type=Application
Categories=Development;IDE;
StartupWMClass=antigravity
EOF
sudo tee /usr/share/applications/antigravity-ide.desktop >/dev/null <<'EOF'
[Desktop Entry]
Name=Antigravity IDE
Comment=Antigravity IDE - standalone agent IDE
Exec=/usr/local/bin/antigravity-ide %U
Icon=antigravity-ide
Terminal=false
Type=Application
Categories=Development;IDE;
StartupWMClass=antigravity-ide
EOF
echo "antigravity $APP_VERSION + ide $IDE_VERSION installed (do NOT run --version: they launch the GUI)"
