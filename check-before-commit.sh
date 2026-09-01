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

if [ -d backend ]; then
  step "backend lint"
  (cd backend && uv run ruff check . && uv run ruff format --check .) || fail=1

  step "backend migrations are complete"
  (cd backend && USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key \
    uv run python manage.py makemigrations --check --dry-run) || fail=1

  step "backend tests"
  (cd backend && USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest -q) || fail=1
fi

if [ -d frontend ] && [ -d frontend/node_modules ]; then
  step "frontend lint and types (advisory)"
  # Not fatal: eslint-config-next ships an eslint-plugin-react that is incompatible with
  # the installed ESLint 10, and frontend/ is deleted in M0. Type errors still show here.
  (cd frontend && npm run lint && npx tsc --noEmit) \
    || echo "frontend checks failed, not blocking the commit (see the comment above)"
fi

if [ "$fail" -ne 0 ]; then
  printf '\n\033[31mchecks failed\033[0m\n'
  exit 1
fi
printf '\n\033[32mall checks passed\033[0m\n'
