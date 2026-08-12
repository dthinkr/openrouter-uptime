#!/usr/bin/env bash
#
# One poll, run from Railway's cron scheduler.
#
# This exists because GitHub's cron drops scheduled runs rather than delaying
# them: under an hourly schedule the collector delivered 43% of its nominal
# rate, and a 15-minute cadence is what the data actually needs. `state` comes
# from up30m, a 30-minute trailing window, so consecutive polls more than 30
# minutes apart leave wall-clock that nothing observed. Fifteen minutes gives
# 15 minutes of slack: a single missed run still leaves no hole, because the
# window before it and the window after it overlap.
#
# Missed observations cannot be backfilled. OpenRouter reports only current
# windows and has no historical endpoint, so the design bias throughout is to
# take an extra sample rather than risk skipping one.
#
# The GitHub Actions workflow stays scheduled as before. Both collectors call
# scripts/should_poll.py first, so whichever arrives first writes and the other
# stands down; no coordination between them is needed.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/dthinkr/openrouter-uptime.git}"
BRANCH="${BRANCH:-main}"
WORKDIR="${WORKDIR:-/data/repo}"

# Only an https remote needs the token woven in; a local path or ssh remote is
# used verbatim, which is also what makes this script testable off Railway.
case "${REPO_URL}" in
  https://*)
    : "${GITHUB_TOKEN:?GITHUB_TOKEN is required (contents:write on this repo)}"
    AUTH_URL="https://x-access-token:${GITHUB_TOKEN}@${REPO_URL#https://}"
    ;;
  *)
    AUTH_URL="${REPO_URL}"
    ;;
esac

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

clone_fresh() {
  # Full history is needed because the push has to fast-forward from a real
  # ancestor; after this the pulls are small.
  log "cloning ${REPO_URL} into ${WORKDIR}"
  rm -rf "${WORKDIR}"
  mkdir -p "$(dirname "${WORKDIR}")"
  git clone --branch "${BRANCH}" "${AUTH_URL}" "${WORKDIR}"
}

if [ ! -d "${WORKDIR}/.git" ]; then
  clone_fresh
fi

cd "${WORKDIR}"

# A container that dies mid-git leaves its lock files behind on the volume, and
# every run after it fails the same way on the same lock. Nothing here retries
# and nothing restarts (restartPolicyType NEVER), so the collector simply stops
# and stays stopped -- quietly, because GitHub Actions keeps committing and the
# data never goes to zero, it only thins out. A stale HEAD.lock did exactly this.
#
# Any lock present at this point is stale by construction: the volume mounts to
# one container at a time, so no git process outlives the container that created
# it, and none has started yet in this one. Sweeping on entry is what turns a
# crashed run into a self-healing one.
clear_stale_git_locks() {
  local lock
  while IFS= read -r lock; do
    [ -n "${lock}" ] || continue
    log "removing stale git lock ${lock}"
    rm -f "${lock}"
  done < <(find "${WORKDIR}/.git" -name '*.lock' -type f 2>/dev/null || true)
}

# Discard anything a previous run left behind mid-write. Everything here is
# either committed or regenerable, so a hard reset is safe and is the only way
# to guarantee a clean base after an interrupted container.
#
# Every step states `|| return 1` rather than leaning on set -e, because set -e
# does not apply inside a function called from a condition: without them a
# failed fetch would fall through to the reset and the function would report
# the last command's status instead of the failure that mattered.
prepare_worktree() {
  git config user.name  "openrouter-uptime-bot" || return 1
  git config user.email "railway@openrouter-uptime" || return 1
  git remote set-url origin "${AUTH_URL}" || return 1
  git fetch --quiet origin "${BRANCH}" || return 1
  git reset --hard --quiet "origin/${BRANCH}" || return 1
  git clean -fdq || return 1
}

clear_stale_git_locks

# The volume is a cache of origin, not a second copy of the truth -- nothing is
# authored here that is not immediately pushed -- so any state it reaches that
# we cannot recover from is cheaper to discard than to diagnose. Re-cloning
# costs one run; leaving the wreckage costs every run after it, because nothing
# restarts and the next cron tick lands on the same broken volume. Locks are
# only the failure mode we have already seen, and the sweep above handles those
# without paying for a clone; this is what catches the ones we have not.
if ! prepare_worktree; then
  log "worktree unusable after clearing locks; discarding it and re-cloning"
  cd /
  clone_fresh
  cd "${WORKDIR}"
  prepare_worktree
fi

# The guard always exits 0 and states its decision on stdout; a crash here
# would surface as empty output, which the case below treats as "not due" only
# after logging it, so a silent guard failure cannot masquerade as a poll.
GUARD="$(python3 scripts/should_poll.py 2>&1 || true)"
log "guard: ${GUARD:-<no output>}"
case "${GUARD}" in
  poll=true*) ;;
  *)
    log "not due, standing down"
    exit 0
    ;;
esac

log "polling"
python3 scripts/poll.py

# README cosmetics. A failure here must not cost the observation, which is
# already written and cannot be re-taken.
python3 scripts/summarize.py || log "summarize failed, continuing"
python3 scripts/readme_events.py || log "readme_events failed, continuing"

git add -A
if git diff --cached --quiet; then
  log "nothing to commit"
  exit 0
fi
git commit --quiet -m "poll $(date -u +%Y-%m-%dT%H:%MZ)"

for attempt in 1 2 3 4 5; do
  if git push --quiet origin "HEAD:${BRANCH}"; then
    log "pushed on attempt ${attempt}"
    exit 0
  fi
  log "push rejected, rebasing (attempt ${attempt})"
  if ! git pull --rebase --quiet origin "${BRANCH}"; then
    git rebase --abort || true
    log "rebase conflicted; dropping this commit, next run re-polls"
    exit 0
  fi
  sleep $(( attempt * 3 ))
done

log "push failed after 5 attempts"
exit 1
