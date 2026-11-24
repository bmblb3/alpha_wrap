#!/usr/bin/env bash
# curl -sL https://raw.githubusercontent.com/bmblb3/alpha_wrap/main/install.sh | bash
set -euo pipefail
D=$HOME/.local/bin
mkdir -p "$D"
curl -fsSL "https://github.com/bmblb3/alpha_wrap/releases/latest/download/alpha-wrap-linux-$(uname -m)" -o "$D/alpha-wrap"
chmod +x "$D/alpha-wrap"
echo "Installed $D/alpha-wrap"
