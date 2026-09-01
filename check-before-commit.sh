#!/usr/bin/env bash
# Runs every check that can run locally, in the order that fails cheapest first.
# Usage: ./check-before-commit.sh   (from the repo root, with staged changes)
set -euo pipefail

cd "$(dirname "$0")"
fail=0
step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

step "em dash in staged changes"
# An em dash is banned everywhere. A spaced "--" standing in for one is banned in
# prose files only, because it is legitimate syntax in code and CLI flags. Inline
# code spans are stripped first, so a doc can quote the banned characters.
strip_code() { sed -e 's/`[^`]*`//g'; }
# Spelled as an escape so this file does not trip its own check.
em_dash=$'\u2014'
if git diff --cached --unified=0 -- . | grep '^+' | grep -v '^+++' | strip_code | grep -n "$em_dash"; then
  echo "found an em dash in added lines: use a comma, a colon, parentheses or two sentences"
  fail=1
fi
if git diff --cached --unified=0 -- '*.md' '*.txt' '*.rst' | grep '^+' | grep -v '^+++' \
    | strip_code | grep -n ' -- '; then
  echo "found ' -- ' used as a dash in prose: rewrite it"
  fail=1
fi

step "lint"
uv run ruff check . || fail=1
uv run ruff format --check . || fail=1

step "migrations are complete"
USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key \
  uv run python manage.py makemigrations --check --dry-run || fail=1

step "tests"
USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest -q || fail=1

if [ "$fail" -ne 0 ]; then
  printf '\n\033[31mchecks failed\033[0m\n'
  exit 1
fi
printf '\n\033[32mall checks passed\033[0m\n'
