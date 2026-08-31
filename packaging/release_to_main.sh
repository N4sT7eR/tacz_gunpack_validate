#!/usr/bin/env bash
#
# Promote develop to main without the test suite.
#
# main is the release branch and ships only what a user runs, so tests/ is
# dropped as part of the merge rather than in a follow-up commit -- that keeps
# main a true descendant of develop, so the next promotion still merges cleanly.
#
# Usage:  packaging/release_to_main.sh [tag]
#         packaging/release_to_main.sh v1.0.0
#
# Nothing is pushed; the commands to run are printed at the end.

set -euo pipefail

SOURCE_BRANCH="develop"
TARGET_BRANCH="main"
EXCLUDED_PATHS=("tests")

if [ -n "$(git status --porcelain)" ]; then
    echo "error: the working tree has uncommitted changes." >&2
    exit 1
fi

original_branch="$(git rev-parse --abbrev-ref HEAD)"
tag="${1:-}"

echo "Promoting ${SOURCE_BRANCH} to ${TARGET_BRANCH}, without: ${EXCLUDED_PATHS[*]}"
git checkout "$TARGET_BRANCH"

if git merge-base --is-ancestor "$SOURCE_BRANCH" "$TARGET_BRANCH"; then
    echo "${TARGET_BRANCH} already contains ${SOURCE_BRANCH}; nothing to promote."
    git checkout "$original_branch"
    exit 0
fi

# The merge is expected to conflict on the excluded paths: they are deleted on
# main and modified on develop. Any other conflict is a real one.
merge_failed=0
git merge --no-ff --no-commit "$SOURCE_BRANCH" || merge_failed=1

unresolved="$(git diff --name-only --diff-filter=U || true)"
unexpected=""
while IFS= read -r path; do
    [ -z "$path" ] && continue
    keep=1
    for excluded in "${EXCLUDED_PATHS[@]}"; do
        case "$path" in "$excluded"/*|"$excluded") keep=0 ;; esac
    done
    [ "$keep" = 1 ] && unexpected="${unexpected}${path}"$'\n'
done <<< "$unresolved"

if [ -n "$unexpected" ]; then
    echo "error: conflicts outside the excluded paths; resolve them by hand:" >&2
    echo "$unexpected" >&2
    git merge --abort
    git checkout "$original_branch"
    exit 1
fi

for excluded in "${EXCLUDED_PATHS[@]}"; do
    git rm -r --force --quiet --ignore-unmatch "$excluded"
    rm -rf "$excluded"
done

version="$(git show "${SOURCE_BRANCH}:pyproject.toml" | sed -n 's/^version = "\(.*\)"/\1/p')"
git commit --quiet -m "Release ${version}

Promotes ${SOURCE_BRANCH} to ${TARGET_BRANCH}. The test suite stays on
${SOURCE_BRANCH}: ${TARGET_BRANCH} carries only what a user runs."

echo
echo "${TARGET_BRANCH} is now at $(git rev-parse --short HEAD) (version ${version})."
git show --stat --oneline HEAD | head -5
echo
if [ -n "$tag" ]; then
    git tag -a "$tag" -m "$tag"
    echo "Tagged ${tag}. To publish:"
    echo "  git push origin ${TARGET_BRANCH} ${tag}"
else
    echo "To publish:"
    echo "  git push origin ${TARGET_BRANCH}"
fi
echo
echo "Returning to ${original_branch}. Run 'git checkout ${TARGET_BRANCH}' to inspect the result."
git checkout "$original_branch"
