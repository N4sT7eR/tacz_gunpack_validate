#!/usr/bin/env bash
#
# Promote develop to main and tag the release.
#
# main carries the same tree as develop, tests included: the branch policy keeps
# formal automated tests on main and removes only throwaway debugging, so main
# is gated by the same suite as everything else rather than shipping untested.
#
# Nothing is pushed. The commands to run are printed at the end, so the release
# is never one keystroke away from being public.
#
# Usage:  packaging/release_to_main.sh           # promote only
#         packaging/release_to_main.sh v1.0.0    # promote and tag

set -euo pipefail

SOURCE_BRANCH="develop"
TARGET_BRANCH="main"

if [ -n "$(git status --porcelain)" ]; then
    echo "error: the working tree has uncommitted changes." >&2
    exit 1
fi

original_branch="$(git rev-parse --abbrev-ref HEAD)"
tag="${1:-}"

# The version lives in two files and a release with them out of step ships an
# executable that misreports itself, so they are compared before anything moves.
project_version="$(git show "${SOURCE_BRANCH}:pyproject.toml" | sed -n 's/^version = "\(.*\)"/\1/p')"
package_version="$(git show "${SOURCE_BRANCH}:src/tacz_validator/__init__.py" \
    | sed -n 's/^__version__ = "\(.*\)"/\1/p')"

if [ -z "$project_version" ]; then
    echo "error: no version found in pyproject.toml on ${SOURCE_BRANCH}." >&2
    exit 1
fi
if [ "$project_version" != "$package_version" ]; then
    echo "error: pyproject.toml says ${project_version}, __init__.py says ${package_version}." >&2
    exit 1
fi

expected_tag="v${project_version}"

if [ -n "$tag" ] && [ "$tag" != "$expected_tag" ]; then
    echo "error: ${tag} does not match version ${project_version}." >&2
    exit 1
fi

# Checked whether or not a tag was asked for. A published tag is never
# re-pointed, so a version that already carries one means develop has not been
# bumped since the last release -- promoting it would put a second "Release
# 0.0.0" on main for a release that already happened.
if git rev-parse -q --verify "refs/tags/${expected_tag}" >/dev/null \
    || git ls-remote --exit-code --tags origin "refs/tags/${expected_tag}" >/dev/null 2>&1; then
    echo "error: ${project_version} is already released as ${expected_tag}." >&2
    echo "       Bump the version on ${SOURCE_BRANCH} before promoting." >&2
    exit 1
fi

echo "Promoting ${SOURCE_BRANCH} to ${TARGET_BRANCH} (version ${project_version})"
git checkout "$TARGET_BRANCH"

if git merge-base --is-ancestor "$SOURCE_BRANCH" "$TARGET_BRANCH"; then
    echo "${TARGET_BRANCH} already contains ${SOURCE_BRANCH}; nothing to promote."
    git checkout "$original_branch"
    exit 0
fi

# --no-ff so the release is one commit to point at, name and revert.
if ! git merge --no-ff -m "Release ${project_version}" "$SOURCE_BRANCH"; then
    echo "error: the merge conflicts; resolve it by hand." >&2
    git merge --abort || true
    git checkout "$original_branch"
    exit 1
fi

echo
echo "${TARGET_BRANCH} is now at $(git rev-parse --short HEAD) (version ${project_version})."
git show --stat --oneline HEAD | head -5
echo
if [ -n "$tag" ]; then
    git tag -a "$tag" -m "$tag"
    echo "Tagged ${tag}. To publish:"
    echo "  git push origin ${TARGET_BRANCH} ${tag}"
else
    echo "To publish:"
    echo "  git push origin ${TARGET_BRANCH}"
    echo "A GitHub Release is built from a tag, so add one to publish binaries."
fi
echo
echo "Returning to ${original_branch}. Run 'git checkout ${TARGET_BRANCH}' to inspect the result."
git checkout "$original_branch"
