#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

TARGET_BRANCH="rewrite/v2-from-scratch"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]]; then
  if git show-ref --verify --quiet "refs/heads/$TARGET_BRANCH"; then
    git checkout "$TARGET_BRANCH"
  else
    git checkout -b "$TARGET_BRANCH"
  fi
fi

# Prune everything except preserved rewrite baseline assets.
for path in * .*; do
  case "$path" in
    "."|".."|".git"|"AGENTS.md"|"specs"|"test"|"docs")
      continue
      ;;
  esac
  rm -rf -- "$path"
done

mkdir -p src/morph_kgc

cat > .gitignore <<'GITIGNORE'
__pycache__/
*.py[cod]
*.so
.pytest_cache/
.mypy_cache/
.venv/
venv/
dist/
build/
*.egg-info/
GITIGNORE

cat > README.md <<'README'
# morph-kgc v2 rewrite branch

This branch is a clean-slate rewrite baseline.

Retained assets:
- `test/` regression suites
- `specs/` planning and contracts
- `AGENTS.md`

New implementation starts under `src/morph_kgc/`.
README

cat > pyproject.toml <<'PYPROJECT'
[build-system]
requires = ["hatchling>=1.11.0"]
build-backend = "hatchling.build"

[project]
name = "morph_kgc"
version = "2.0.0a0"
description = "Rewrite baseline for Morph-KGC v2"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
test = ["pytest>=8.0.0,<9.0.0"]

[project.scripts]
morph-kgc = "morph_kgc.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/morph_kgc"]
PYPROJECT

cat > src/morph_kgc/__init__.py <<'PYINIT'
"""morph_kgc v2 rewrite package."""


def materialize(config, python_source=None):
    raise NotImplementedError("morph_kgc v2 rewrite in progress")


def materialize_oxigraph(config, python_source=None):
    raise NotImplementedError("morph_kgc v2 rewrite in progress")


def materialize_set(config, python_source=None):
    raise NotImplementedError("morph_kgc v2 rewrite in progress")


def materialize_kafka(config, python_source=None):
    raise NotImplementedError("morph_kgc v2 rewrite in progress")


def translate_to_rml(mapping_path):
    raise NotImplementedError("morph_kgc v2 rewrite in progress")
PYINIT

cat > src/morph_kgc/__main__.py <<'PYMAIN'
import sys


def main():
    print("morph-kgc v2 rewrite: CLI not implemented yet", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
PYMAIN

cat > specs/COMPATIBILITY.md <<'COMPAT'
# Compatibility Contract (V2)

## Scope
V2 must preserve user-visible behavior for supported YARRRML/RML/FNML scenarios covered by retained regression tests under `test/`.

## Initial Guarantees
- Package name remains `morph_kgc`.
- Public entry points reserved:
  - `materialize`
  - `materialize_oxigraph`
  - `materialize_set`
  - `materialize_kafka`
  - `translate_to_rml`
- CLI command remains `morph-kgc`.

## Performance Targets
- Establish baseline from legacy branch and require measurable improvements before release.

## Validation Gate
- No release until conformance + performance test gates are green.
COMPAT

echo "Running baseline verification test..."
set +e
PYTHONPATH=src python -m pytest test/issues/issue_328/test_prefixes_yarrrml.py
TEST_EXIT=$?
set -e

echo "Baseline test exit code: $TEST_EXIT"
exit 0
