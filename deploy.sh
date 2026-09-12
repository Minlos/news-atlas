#!/bin/bash
# Push this repo to GitHub, then pull it onto minlos.site.
# Does not run the classifier. To rebuild the map on the server:
#   ssh minlos@minlos.site 'cd ~/news-atlas && ./run.sh'
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
branch="$(git branch --show-current)"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "uncommitted changes — commit first" >&2
  git status -sb
  exit 1
fi
git push origin "$branch"
ssh -o BatchMode=yes minlos@minlos.site "bash -s" <<EOS
set -euo pipefail
cd "\$HOME/news-atlas"
git fetch origin
git checkout -q "$branch"
git pull --ff-only origin "$branch"
echo "code \$(git rev-parse --short HEAD) on minlos.site"
EOS
echo "live https://minlos.site/news/ (last map rebuild; classifier is manual)"
