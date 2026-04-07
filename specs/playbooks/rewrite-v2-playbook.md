# Rewrite V2 Playbook

## Goal
Reset the repository to a clean rewrite baseline while preserving:

- `test/` (treated as end-to-end regression suite)
- `specs/`
- `AGENTS.md`
- `docs/` (if present)

Then scaffold a fresh `morph_kgc` package for a full rewrite.

## Preconditions

1. Run from repository root.
2. Work on branch `rewrite/v2-from-scratch`.
3. Keep existing uncommitted `specs/` and `AGENTS.md` changes.

## Steps

1. Create branch `rewrite/v2-from-scratch` if missing.
2. Prune repository files/directories except:
   - `.git/`
   - `AGENTS.md`
   - `specs/`
   - `test/`
   - `docs/` (if exists)
3. Recreate minimal project scaffolding:
   - `pyproject.toml`
   - `README.md`
   - `src/morph_kgc/__init__.py`
   - `src/morph_kgc/__main__.py`
   - `.gitignore`
4. Add a compatibility contract:
   - `specs/COMPATIBILITY.md`
5. Verify baseline by running:
   - `PYTHONPATH=src python -m pytest test/issues/issue_328/test_prefixes_yarrrml.py`
6. Record outcome and next actions.

## Success Criteria

- Branch exists and is checked out.
- Legacy runtime code is removed.
- Tests/specs/agent instructions are preserved.
- New package skeleton exists.
- At least one retained regression test is executed to establish baseline status.
