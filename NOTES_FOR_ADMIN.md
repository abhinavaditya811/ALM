# NOTES FOR ADMIN — v0.1 build run (Tasks 0–4)

Scope of this run: Tasks 0 through 4 only. Tasks 5+ (harness: eval set, scoring,
gate, corrections, registry, loop) are intentionally OUT of scope and NOT built.

## Environment note (important for review)

- Three Python interpreters are present on this machine. I standardized on
  `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3` (Python 3.12.5),
  which is what `python3` resolves to by default and where `pip install -e ".[dev]"`
  put the deps. All `pytest`/`mypy`/`ruff` results below were run with that
  interpreter. If you run `pytest`/`mypy` directly and see "No module named
  pytest", your shell's `pytest` may point at a different interpreter
  (e.g. anaconda). Use the 3.12 framework python, or reinstall into your default.

---

## DECISIONS LOGGED

### D1 (Task 0/1) — schema failed to import; applied a minimal import-alias fix

**Symptom:** `import schema.models` raised
`TypeError: unsupported operand type(s) for |: 'NoneType' and 'NoneType' — Unable
to evaluate type annotation 'date | None'` on every interpreter (3.12 and 3.13).

**Root cause:** In `WORecord`, the field is named `date` and its type is also
`date` (`date: date | None = None`). Because the module uses
`from __future__ import annotations`, the annotation `"date | None"` is evaluated
lazily by pydantic. During that evaluation the field's own class-level default
(`date = None`) shadows the imported `datetime.date`, so the annotation resolves
to `None | None` and raises. This makes the whole project unimportable — Task 0
(a hard prerequisite for everything) cannot pass without resolving it.

**Fix applied (minimal, no shape/logic change):** aliased the import
(`from datetime import date as _date`) and referenced the field type as
`_date | None`. The field is STILL named `date`, STILL a date, and the JSON/wire
contract, defaults, and all validators are byte-for-byte unchanged. This is an
import-resolution fix, not a redesign of the schema.

**Why I did not just log-and-skip:** Task 0 explicitly says "nothing else is safe
to build until this passes," and it also authorizes fixing so imports succeed. The
alias is the smallest possible change that unblocks the entire build without
altering any data shape or validator behavior.

**If you prefer a different resolution:** an equivalent option is to rename the
field itself (e.g. `wo_date`), but that WOULD change the data contract, so I did
not do it. Flagging for your call.

### D2 (Task 0) — ruff UP037 autofix on models.py

Ruff flagged 4 redundant-quote forward-ref annotations in the pre-existing
`models.py` (e.g. `-> "Classification"`). With `from __future__ import annotations`
these quotes are unnecessary; ruff's autofix removed them. Behavior-identical,
no shape change. Done only to keep `ruff check src tests` green (a documented
project command).

### D3 (git workflow) — no `gh`/remote available; PRs must be opened manually

This machine has no `gh` CLI and the repo has no remote. Per BUILD_PLAN.md's
fallback, I still created the stacked branches (`task-0` from `main`, each
`task-N` from `task-(N-1)`) with one commit per task, unmerged. **You must add a
remote, push the branches, and open the stacked PRs manually** (base each PR on
the previous task's branch, not `main`). No history was rebased or force-pushed.

Branches (in stack order): `main` → `task-0` → `task-1` → `task-2` → `task-3`
→ `task-4`.

---

## TASK STATUS

### Task 0 — Confirm the repo runs green — ✅ DONE
- Added `pyproject.toml` (was empty): setuptools src-layout, deps `pydantic>=2`,
  dev deps `pytest`/`mypy`/`ruff`, pytest/mypy/ruff config.
- Added `src/schema/__init__.py` and a Task-0 smoke test (`tests/test_smoke.py`).
- Applied D1 + D2 above.
- Verified: `pytest -q` PASS, `mypy src` PASS (no issues), `ruff check` PASS.

(Tasks 1–4 status appended as completed.)
