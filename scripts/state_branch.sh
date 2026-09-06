#!/usr/bin/env bash
# Run from the repository root. The worktree shares checkout's Git credentials.
set -euo pipefail

case "${1:-}" in
  prepare)
    # A failed remote lookup must not be mistaken for a new, empty state branch.
    remote_ref=$(git ls-remote --heads origin refs/heads/state)
    if [[ -n "$remote_ref" ]]; then
      git fetch origin refs/heads/state
      git worktree add --detach .state FETCH_HEAD
    else
      git worktree add --detach .state HEAD
      git -C .state checkout --orphan state
      git -C .state rm -rf --ignore-unmatch .
    fi
    ;;
  save)
    git -C .state config user.name 'github-actions[bot]'
    git -C .state config user.email '41898282+github-actions[bot]@users.noreply.github.com'
    git -C .state add status.json history.jsonl
    git -C .state commit -m "Record certificate check ${GITHUB_RUN_ID:-local} attempt ${GITHUB_RUN_ATTEMPT:-1}"
    # Never force-push: a concurrent external edit should fail visibly.
    git -C .state push origin HEAD:refs/heads/state
    ;;
  *)
    echo 'Usage: bash scripts/state_branch.sh prepare|save' >&2
    exit 2
    ;;
esac
