# Architecture at a glance

> On-demand reference for Claude Code. Read before changing project structure or
> the harness. This is the "how it fits together" — not strategy, not rationale.

## The two concepts

SKILL — a named, repeatable analytical procedure over work-order data with a fixed
input/output contract, a version, and a metric. Discrete and named so it can be
measured and improved in isolation. The skill boundary is the measurement boundary.

HARNESS — the machinery that measures a skill against a frozen eval set and lets it
improve safely (human-gated, never autonomous).

## v0.1 scope

One skill: `failure_vs_suspension` (classify a work order as failure /
precautionary / unclassifiable, with normalized failure_mode, calibrated
confidence, evidence_span, needs_review). Plus the full harness around it.

## The five harness components

1. FROZEN EVAL SET — human-labeled records, read-only, never used as few-shot.
   The immovable ruler. Everything depends on it being honest.
2. SCORING RUNNER — skill version -> metrics (precision/recall/F1 + calibration
   error). Deterministic, logged. Pure computation.
3. REGRESSION GATE — a version ships only if it does not regress any tracked
   metric below the prior best (within tolerance).
4. CORRECTION CAPTURE — human overrides logged as candidate labels with full
   provenance. v0.1: STORE ONLY. No promotion, no retrain.
5. VERSION REGISTRY — every version + its score + rollback. The audit trail that
   makes improvement visible (v1=0.81, v2=0.86, ...).

## Directory map

```
src/
  skills/base/                 # Skill protocol (contracts, version, metric)
  skills/failure_vs_suspension/# the one v0.1 skill
  harness/evalset/             # frozen set loader (read-only) + integrity check
  harness/scoring/             # scoring runner -> metrics (pure)
  harness/gate/                # regression gate (pure)
  harness/corrections/         # capture + candidate store (store only)
  harness/registry/            # version + score store + rollback
  llm/                         # single client, versioned prompts, retry+validate
  api/                         # batch-classify HTTP API (live callers, e.g. ReliaSoft)
  schema/models.py             # pydantic contracts — source of truth
data/
  evalset/                     # frozen labeled records (the ruler) — READ ONLY
  samples/                     # messy sample work orders for dev
tests/                         # harness self-tests + skill benchmark
```

## The loop (how improvement flows)

new data -> skill classifies -> engineer reviews & corrects -> correction captured
-> [deferred human step: vetted corrections promoted into eval set / few-shot]
-> someone improves the skill -> scoring runner scores it -> gate decides ->
registry records. A human sits at every gate. v0.1 builds all of this EXCEPT the
bracketed promotion step.

## Two callers of a skill

The harness (scoring runner) and the API (`src/api/`) both call a skill through
the same `Skill` protocol (`src/skills/base.py`) — neither bypasses it:

- HARNESS: scores a skill against the FROZEN EVAL SET, offline/dev-time. Answers
  "did this version get better or worse?"
- API: classifies live, real work orders for an external caller (e.g. ReliaSoft),
  online/operational. Answers "what is this one real record?" Batched, per-record
  error isolation, requires auth, backend chosen server-side (never per-request).

## Hard invariants

- LLM does language; code does arithmetic. Never mixed.
- Eval set is sacred: read-only, integrity-checked, never few-shot material.
- No autonomous improvement. Capture only in v0.1.
- Every output carries evidence_span + skill_version (provenance).
- Unclassifiable / "insufficient data" are valid, visible outputs — never guess.