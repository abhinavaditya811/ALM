# BUILD_PLAN.md — v0.1 Ordered Task List

> Work these IN ORDER. Each task ends in a runnable, tested state. Do not start a
> task until the previous task's tests pass.
> Follow CLAUDE.md and docs/architecture.md strictly. Stay within v0.1 non-goals.
> If blocked or a decision is genuinely ambiguous: do NOT guess and build on it —
> log the question in NOTES_FOR_ADMIN.md and move to the next INDEPENDENT task.

## Git workflow — stacked PRs (one per task)

Each task gets its own branch and its own PR, stacked on the previous task so
dependencies flow forward without needing anything merged to `main` mid-run:

1. For Task N, cut branch `task-N` FROM the previous task's branch (`task-(N-1)`),
   not from `main`. Task 0/1 branches from `main`.
2. Do the work; run `pytest -q` and `mypy src` until both pass; commit.
3. Open a PR for `task-N` with its BASE set to `task-(N-1)` (the branch it was cut
   from), NOT `main`. This keeps each PR's diff limited to that task's own changes.
   Title it clearly (e.g. "Task 6: scoring runner").
4. Do NOT merge it. Leave the PR open for morning review. Cut `task-(N+1)` from
   `task-N` and continue.

Requires a remote with push access and an authenticated `gh` CLI. If PRs cannot be
opened (local-only repo, no auth), STILL create the stacked branches as above,
commit per task, and note in NOTES_FOR_ADMIN.md that PRs must be opened manually.

Do NOT rebase or force-push a lower branch after higher branches are stacked on it
— if an early task needs a fix, log it in NOTES_FOR_ADMIN.md rather than rewriting
history the stack depends on.

Legend: [ ] todo · each task lists its "DONE WHEN" gate.

---

## Task 0 — Confirm the repo runs green
Prereq for everything. Do this first.
- Run `pip install -e ".[dev]" --break-system-packages`.
- Run `pytest -q` and `mypy src`.
- If anything fails to install or import, fix packaging/config ONLY (do not touch
  logic). If you cannot make it run, STOP and write the blocker in
  NOTES_FOR_ADMIN.md — nothing else is safe to build until this passes.
DONE WHEN: `pytest -q` and `mypy src` both run and pass on the starter skeleton.

## Task 1 — Lock down the schema
The schema already exists in src/schema/models.py. Do not redesign it.
- Ensure it imports cleanly and all validators behave.
- Extend tests/test_schema.py to cover: valid failure; failure missing mode
  (reject); non-failure with a mode (reject); empty evidence + high confidence
  (reject); unclassifiable with low confidence + empty evidence (accept);
  EvalCase and Correction consistency validators.
DONE WHEN: test_schema.py covers every validator branch and passes.

## Task 2 — LLM client (src/llm/client.py)
- One function that takes a prompt + structured-output schema, calls the model at
  temperature 0, validates the JSON response against the pydantic model, retries
  up to 2x on schema violation, and logs prompt hash/model/tokens/latency.
- Prompts load from src/llm/prompts/ as versioned files; no inline prompts.
- For testability, the model call must be injectable/mockable so tests never hit
  a real API.
DONE WHEN: a unit test with a mocked model gets a validated object back, and a
malformed-then-valid response exercises the retry path.

## Task 3 — Skill base protocol (src/skills/base.py)
- Define the Skill protocol: run(record: WORecord) -> Classification, plus
  properties version, metric_name, and a reference to its eval set path.
- No logic yet; this is the contract every future skill implements.
DONE WHEN: the protocol type-checks and a trivial dummy skill can satisfy it in a
test.

## Task 4 — The failure_vs_suspension skill (src/skills/failure_vs_suspension/)
- skill.py implements the protocol using the LLM client.
- prompts/failure_vs_suspension_v1.txt: the classification prompt — domain frame,
  the CLOSED failure-mode list, sharp failure/precautionary/unclassifiable
  definitions, require an evidence_span, calibrated (low-when-unsure) confidence.
- examples.py: 6-10 few-shot examples spanning all categories and multiple
  vocabularies. These MUST NOT come from data/evalset/ (forbidden).
- Empty/near-empty note => unclassifiable, needs_review, no LLM call.
DONE WHEN: the skill runs over data/samples/ with a mocked model in tests and
returns schema-valid Classifications; the empty-note path is covered.

## Task 5 — Frozen eval set loader (src/harness/evalset.py)
- Load data/evalset/failure_vs_suspension.jsonl into list[EvalCase], read-only.
- Integrity check on load (count + hash); refuse to run if the set looks mutated
  unexpectedly. Never expose a write path.
DONE WHEN: loader returns validated EvalCases and a mutation/format-error test
raises rather than silently proceeding.

## Task 6 — Scoring runner (src/harness/scoring.py) — PURE
- Given a skill's Classifications + the EvalCases, compute a SkillScore:
  failure_precision (headline), failure_recall, macro_f1, calibration_error (ECE:
  bin by confidence, compare stated vs actual accuracy), n_cases, run_id.
- No I/O, no LLM. Deterministic. This is the ruler-reading, so it must be exact.
DONE WHEN: known-answer test — a hand-built set of predictions vs. truths yields
the precomputed metric values within tolerance.

## Task 7 — Regression gate (src/harness/gate.py) — PURE
- Compare a candidate SkillScore to the registry's current best. Return a
  GateResult: PASS only if headline metric >= best (within tolerance) AND no
  tracked metric regresses beyond limit; else FAIL with a specific reason.
DONE WHEN: tests show it PASSES a clear improvement and FAILS a regression, with
the reason string correct in both.

## Task 8 — Version registry (src/harness/registry.py)
- Persist every VersionRecord (version + SkillScore + timestamp). Support marking
  a current version and rolling back to a prior one.
DONE WHEN: register two versions, roll back, and a test confirms the current
pointer and history are correct.

## Task 9 — Correction capture (src/harness/corrections.py) — STORE ONLY
- Persist a Correction (model output + human-corrected values + who/when) to a
  candidate pool store. NO promotion, NO eval-set write, NO retrain. That is a
  deferred human step — do not build it.
DONE WHEN: a correction round-trips to the store with full provenance; a test
asserts nothing writes to data/evalset/.

## Task 10 — End-to-end "the machine turns" test (tests/test_harness_loop.py)
- With a mocked model: score skill v1 over the eval set -> register it -> score a
  v2 (simulate a changed prompt via a different mock) -> run the gate -> registry
  records the outcome -> capture one correction.
- This is the proof that the loop turns. It ties every component together.
DONE WHEN: the full loop test passes and demonstrates a gate decision + a recorded
version history + a captured correction.

---

## When finished (or fully blocked)
Write NOTES_FOR_ADMIN.md with:
- Completed tasks (each with test status).
- Skipped tasks and exactly why.
- Every question/ambiguity you logged, with your reasoning.
- The real failure_precision if the skill was scored on any data (do NOT hide a
  weak number).
- What you would do next.

## Do NOT (v0.1 non-goals — repeated so they are not forgotten)
No second skill (scaffold base only). No Weibull/statistical modeling. No
ReliaSoft/360Navigator export. No live CMMS integration. No capture-side/voice. No
dashboard. No fine-tuning. No correction promotion / autonomous improvement.