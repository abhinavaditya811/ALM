# Project Context

Reliability-analysis "skills" over messy free-text maintenance work orders, plus a
harness that scores each skill against a frozen eval set and lets it improve safely.
v0.1 builds ONE skill (failure-vs-suspension classifier) + the full harness loop.

Core rule: the LLM does language (classify, normalize vocabulary, phrase text);
code does counting, scoring, and gating. They never cross.

Deeper context is in @docs/architecture.md (read it before changing structure).
Data contracts are real code in `src/schema/models.py` — read before editing types.

## Commands

- Install:      `pip install -e ".[dev]" --break-system-packages`
- Test:         `pytest -q`
- Type check:   `mypy src`
- Lint:         `ruff check src tests`
- Score a skill:`python -m harness.scoring --skill failure_vs_suspension`
- Run the API:  `uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000`
  (requires `ANALYTIXLLM_API_KEY` set; picks the backend via `ANALYTIXLLM_BACKEND`,
  default `deepseek`)

## Working Rules

- IMPORTANT: run `mypy src` and `pytest -q` after every code change; do not
  consider a change done until both pass.
- Make minimal changes — do not refactor unrelated code.
- pydantic models in `src/schema/models.py` are the source of truth for all data
  shapes. Extend them there; never redefine a shape inline in a module.
- Scoring, gate, and metric code must be PURE functions: no I/O, no LLM calls.
  Keep them deterministic and unit-testable.
- All LLM calls go through `src/llm/` only. No LLM calls anywhere else.
- Never fabricate: every classification carries an `evidence_span`; if none can
  be given, lower confidence. `unclassifiable` is a valid, first-class output.
- The frozen eval set (`data/evalset/`) is READ-ONLY. Never write to it in code.
  Using eval cases as few-shot examples is forbidden (it corrupts the ruler).
- NO auto-promotion of corrections, NO retraining, NO autonomous self-improvement
  in v0.1. Corrections are captured and stored only. Human promotion is deferred.
- When unsure between two approaches, explain both and let me choose — do not make
  architectural decisions silently.
- Create separate commits per logical change, not one giant commit.
- No file should be more than 400 lines of code, we don't want to make any file chunky and follow SOLID principles.

## Verification

- After changing a skill: run its scorer and report the real metric (do not hide a
  weak number). A change ships only if the regression gate PASSES.
- After changing schema: run `mypy src` and `pytest -q`; both must pass.

## Non-goals (do not drift into these)

No second skill yet (scaffold the base protocol only). No Weibull/statistical
modeling. No live CMMS integration (ReliaSoft calling our batch-classify API is
not us integrating with a CMMS ourselves — see `src/api/`). No capture-side/voice.
No dashboard framework. No fine-tuning.