# failure_vs_suspension eval set — STATUS: SYNTHETIC PLACEHOLDER

`failure_vs_suspension.jsonl` (50 records) is **not** real CMMS data and was
**not** produced by two independent labelers + adjudication as described in
`EvalCase`'s docstring. Each note was authored so its label is correct by
construction, to exercise the harness end-to-end (loader, scoring, gate,
registry) before real labeled data exists.

Distribution: 30 failure (5-6 per failure_mode across all 6 modes), 12
precautionary, 8 unclassifiable.

`failure_vs_suspension.manifest.json` pins `count` + `sha256` of the `.jsonl`
file; the loader (`src/harness/evalset.py`) refuses to load if either drifts,
so any edit here must regenerate the manifest.

**Before reporting any real `failure_precision`/recall/F1/calibration number
to a stakeholder, this file must be replaced with a genuinely human-labeled
set** (ideally two independent labelers + adjudication, per the architecture
doc) and the manifest regenerated. Until then, treat every score produced
against this set as a plumbing check, not a reliability metric.
