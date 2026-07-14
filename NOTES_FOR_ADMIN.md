# NOTES FOR ADMIN — v0.1 build run (Tasks 0–4, then 5–10)

## Addendum — Tasks 5–10 (harness build-out)

Scope of this run: the full harness (eval set loader, scoring, gate, registry,
corrections, end-to-end loop test). Stacked branches `task-5` → `task-10`, each
based on the previous, one PR per task (unmerged, per the existing convention):
PRs #6–#11 against `abhinavaditya811/ALM`.

### DECISIONS LOGGED (D6+)

**D6 — the eval set is a SYNTHETIC PLACEHOLDER, not real labeled data.**
No labeled work-order dataset exists anywhere in this repo or elsewhere I could
find (confirmed by search before building). Per your explicit sign-off, I
authored 50 records by hand (`data/evalset/failure_vs_suspension.jsonl`) where
each note was written to match its label — NOT produced by two independent
labelers + adjudication as `EvalCase`'s docstring describes. Flagged loudly in
`data/evalset/README.md`. **Every metric produced against this set (including
the numbers below) is a plumbing check, not a reliability number — do not quote
it to a stakeholder.** Replace the `.jsonl` + regenerate the manifest with real
labeled data before that's true.

**D7 — eval set integrity check design: count + sha256 manifest.**
`src/harness/evalset.py` pairs `failure_vs_suspension.jsonl` with a sibling
`failure_vs_suspension.manifest.json` (`{"count", "sha256"}`). The loader
refuses to load if either drifts. No write function exists anywhere in the
module — if you ever need to legitimately edit the eval set, you must also
regenerate the manifest by hand (e.g. `shasum -a 256`).

**D8 — regression gate tolerance is a judgment call: 0.02 flat, per metric.**
`src/harness/gate.py`'s `METRIC_TOLERANCE = 0.02` applies uniformly to all 4
tracked metrics (failure_precision, failure_recall, macro_f1 as
higher-is-better; calibration_error as lower-is-better). Not derived from any
data — a reasonable starting default, isolated in one constant if you want it
stricter/looser or per-metric.

**D9 — registry/corrections storage is gitignored, unlike the eval set.**
`data/registry/` and `data/corrections/` are runtime state produced by
*actually running* the harness (not source, not the frozen ruler), so I added
them to `.gitignore` rather than committing empty/placeholder files. Nothing
has been legitimately registered yet (no real scoring run has happened outside
tests and one manual sanity check). Easy to un-gitignore later if you'd rather
track the audit trail in git history from the start.

**D10 — Task 10's "v2" is simulated via a version-tagged subclass, not a real
second prompt.** BUILD_PLAN Task 10 asks to "simulate a changed prompt via a
different mock." Since building an actual second prompt/skill is explicitly
out of v0.1 scope (non-goals), `tests/test_harness_loop.py` defines a
test-local `_SimulatedV2Skill(FailureVsSuspensionSkill)` that only overrides
the `VERSION` class attribute, paired with a different mocked backend. This
exists only in the test file — nothing under `src/` implies a real v2 exists.

### TASK STATUS (5–10)

All six DONE. Full suite (Tasks 0–10): **73 passed**, `mypy src` / `mypy tests`
clean, `ruff check src tests` clean, after every task. One real bug caught by
`mypy` mid-build (Task 6: a loop-variable type conflict in
`harness/scoring.py`'s `_match`), fixed before commit — see PR #7.

### REAL METRIC / SCORING (still not a real number — see D6)

As a plumbing sanity check (not committed as a test, run manually), the real
`failure_vs_suspension` skill scored against the real 50-record placeholder
set, with a mocked backend that always predicts `failure`/`Bearing Failure`
at confidence 0.9:
- `failure_precision` = 0.612 (30 true failures / 49 predicted-failure — the
  skill's own empty-note shortcut correctly left 1 case as `unclassifiable`
  with zero LLM calls for that one)
- `failure_recall` = 1.0
- `macro_f1` = 0.327
- `calibration_error` = 0.302

These numbers say nothing about real classification quality — they say the
wiring between the loader, the skill, and the scorer is correct. Do not use
them for anything else.

### WHAT I'D DO NEXT
1. Get the stacked PRs (#6–#11) reviewed and merged in order.
2. Replace `data/evalset/failure_vs_suspension.jsonl` with real labeled work
   orders (ideally two independent labelers + adjudication) and regenerate
   the manifest — this is the one thing standing between "the harness runs"
   and "the harness tells you something true."
3. Once real data is in, run the scorer for real and report the actual
   `failure_precision` — do not reuse the placeholder numbers above.
4. Decide whether to un-gitignore `data/registry/`/`data/corrections/` once a
   real run produces a registry/correction history worth keeping in git.

---

# Original notes (Tasks 0–4)

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

### D4 (Task 4) — prompt file lives in `src/llm/prompts/`, not the skill dir

BUILD_PLAN Task 4 names the prompt `prompts/failure_vs_suspension_v1.txt`, which
reads as skill-local. But Task 2 says "prompts load from `src/llm/prompts/`" and
`docs/architecture.md` lists `llm/` as the home for "versioned prompts". I put the
prompt at `src/llm/prompts/failure_vs_suspension_v1.txt` and load it via
`load_prompt(...)` so there is ONE prompt home behind the single LLM entry point.
Easy to relocate if you prefer skill-local prompts; flagging so it's a conscious
choice, not a silent one.

### D5 (Task 4) — added `ClassificationDraft` to `schema/models.py`

To keep the "LLM does language, code does arithmetic/provenance" invariant, the
model returns only language fields (category, failure_mode, confidence,
evidence_span). Code stamps `wo_id`/`skill_version` and derives `needs_review`
(a threshold decision). That language-only shape is `ClassificationDraft`. Per
CLAUDE.md ("extend shapes in models.py; never redefine inline") I added it to the
source-of-truth file rather than defining it in the skill module. It mirrors
`Classification`'s consistency validators so an invalid draft triggers the
client's retry. This is an additive extension, not a change to existing shapes.

---

## TASK STATUS

### Task 0 — Confirm the repo runs green — ✅ DONE
- Added `pyproject.toml` (was empty): setuptools src-layout, deps `pydantic>=2`,
  dev deps `pytest`/`mypy`/`ruff`, pytest/mypy/ruff config.
- Added `src/schema/__init__.py` and a Task-0 smoke test (`tests/test_smoke.py`).
- Applied D1 + D2 above.
- Verified: `pytest -q` PASS, `mypy src` PASS (no issues), `ruff check` PASS.

### Task 1 — Lock down the schema — ✅ DONE
- `tests/test_schema.py` covers every validator branch: valid failure; failure
  missing mode; failure_mode outside vocabulary; non-failure with a mode; empty
  evidence + high confidence (reject); unclassifiable low-confidence empty
  evidence (accept); confidence out of range; negative cost; and both directions
  of the EvalCase and Correction consistency validators.
- No schema redesign (only the D1 import alias from Task 0).
- Verified: full suite passes, mypy + ruff clean.

### Task 2 — LLM client — ✅ DONE
- `src/llm/client.py`: `call_structured(prompt, schema, backend)` calls the model
  at temperature 0, parses JSON (tolerates a markdown fence), validates against a
  caller pydantic model, retries up to `max_retries` (default 2) on JSON/schema
  violations appending a repair hint, and logs prompt hash/model/tokens/latency.
  `StructuredCallError` on exhaustion. `load_prompt` reads versioned files.
- Model call is injected via `ModelBackend` Protocol → fully mockable; NO provider
  import, NO network, NO API key needed to build or test.
- Tests (`tests/test_llm_client.py` + `tests/fakes.py`) cover happy path,
  temperature=0, fence stripping, malformed-then-valid retry, schema-violation
  -then-valid retry, and retry exhaustion.

### Task 3 — Skill base protocol — ✅ DONE
- `src/skills/base.py`: `runtime_checkable` `Skill` Protocol —
  `run(record) -> Classification` plus `version`, `metric_name`, `eval_set_path`.
  Contract only, no logic.
- Test: a `DummySkill` satisfies it structurally (verified with `mypy tests`) and
  at runtime (`isinstance`), and its `run()` returns a valid `Classification`.

### Task 4 — failure_vs_suspension skill — ✅ DONE
- `src/skills/failure_vs_suspension/skill.py` implements the protocol using the
  LLM client. Empty/near-empty note (< 3 non-space chars) → unclassifiable,
  needs_review, NO LLM call. Code stamps provenance and derives needs_review
  (threshold 0.6). See D5.
- `src/llm/prompts/failure_vs_suspension_v1.txt`: domain frame, CLOSED failure-mode
  list, sharp failure/precautionary/unclassifiable definitions, mandatory
  evidence_span, calibrated (low-when-unsure) confidence. See D4.
- `examples.py`: 10 hand-written synthetic few-shot examples spanning all three
  categories, all six failure modes, and varied vocab/abbreviations. NOT from
  data/evalset/ (that dir does not exist; forbidden as few-shot anyway).
- `data/samples/work_orders.jsonl`: 12 synthetic messy work orders (plausible but
  fake), including empty/near-empty and administrivia notes.
- Tests (`tests/test_failure_vs_suspension.py`) run the skill over all samples
  with a mocked backend → schema-valid Classifications; cover protocol
  conformance, provenance stamping, derived needs_review, the empty-note no-LLM
  path (asserts zero backend calls), and the retry path.

## OVERALL VERIFICATION (after Task 4, full suite)
- `pytest`: **39 passed** (4 warnings — pre-existing `datetime.utcnow` deprecation
  in models.py, which I did not touch per the no-redesign rule).
- `mypy src`: Success, no issues (9 source files). `mypy tests`: also clean.
- `ruff check src tests`: All checks passed.

## REAL METRIC / SCORING
Not applicable yet. Scoring (Task 6) and the frozen eval set (Task 5) are OUT of
scope for this run, and `data/evalset/` was deliberately NOT created. The skill
has therefore NOT been scored against any ruler — there is no `failure_precision`
number to report, and I am not inventing one. All skill tests use a MOCKED model,
so they prove the plumbing and contracts, not real classification accuracy.

## SKIPPED (out of scope by instruction)
Tasks 5–10 (frozen eval set loader, scoring runner, regression gate, version
registry, correction capture, end-to-end loop test). Skipped because this run was
scoped to Tasks 0–4 only. No `data/evalset/` was created (correct — that is Task
5+). No harness package exists yet.

## WHAT I'D DO NEXT
1. Open the stacked PRs manually (see D3) once a remote/`gh` is available.
2. Task 5: build `src/harness/evalset.py` with the read-only loader + integrity
   (count+hash) check, and create the frozen `data/evalset/` set.
3. Continue Tasks 6–10 per BUILD_PLAN. When Task 6 scoring lands, run the skill
   against the real eval set and report the true `failure_precision`.
4. Consider (with your sign-off) modernizing `datetime.utcnow` → timezone-aware
   `datetime.now(UTC)` in models.py to clear the deprecation warnings; left
   untouched here to respect "do not redesign the schema."
