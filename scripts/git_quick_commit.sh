#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/git_quick_commit.sh \"commit message\""
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

msg="$*"
branch="$(git rev-parse --abbrev-ref HEAD)"

git add -A

if git diff --cached --quiet; then
  echo "No staged changes. Nothing to commit."
  exit 0
fi

git commit -m "${msg}"
git push -u origin "${branch}"

echo "Done: committed and pushed to origin/${branch}"
