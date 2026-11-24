#!/usr/bin/env bash
# Build the static `wrap` binary and attach it to a GitHub Release.
# Usage: ./publish-binary.sh REPO TAG    e.g. ./publish-binary.sh alpha-wrap v0.1.0
# REPO is either "name" (owned by your gh user) or "owner/name".
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 REPO TAG" >&2
  exit 1
fi

repo=$1
tag=$2
if [[ "$repo" != */* ]]; then
  repo="$(gh api user --jq .login)/$repo"
fi

dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
asset="$dir/bin/alpha-wrap-linux-$(uname -m)"

docker build -f "$dir/Dockerfile" --target export --output "type=local,dest=$dir/bin" "$dir"
mv "$dir/bin/wrap" "$asset"

if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
  gh release upload "$tag" "$asset" --repo "$repo" --clobber
else
  gh release create "$tag" "$asset" --repo "$repo" --title "$tag" \
    --notes "Static alpha-wrap binary (Linux, no dependencies)"
fi
