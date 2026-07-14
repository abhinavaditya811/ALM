"""Few-shot examples for the failure_vs_suspension classification prompt.

These are HAND-WRITTEN synthetic demonstrations spanning every category, every
closed failure mode, and multiple maintenance vocabularies/abbreviations. They
are deliberately NOT drawn from data/evalset/ — using eval cases as few-shot
would corrupt the ruler (forbidden by CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from schema.models import Category, ClassificationDraft


@dataclass(frozen=True)
class FewShot:
    """One demonstration: a messy input note + the expected language output."""
    note: str
    asset_type: str | None
    expected: ClassificationDraft


FEW_SHOT: list[FewShot] = [
    FewShot(
        note="pmp brg seized overnight, unit tripped, replaced brg + shaft",
        asset_type="centrifugal pump",
        expected=ClassificationDraft(
            category=Category.FAILURE,
            failure_mode="Bearing Failure",
            confidence=0.93,
            evidence_span="brg seized",
        ),
    ),
    FewShot(
        note="mech seal weeping at gland, product on floor, swapped seal cartridge",
        asset_type="process pump",
        expected=ClassificationDraft(
            category=Category.FAILURE,
            failure_mode="Seal/Packing Leak",
            confidence=0.9,
            evidence_span="mech seal weeping",
        ),
    ),
    FewShot(
        note="motor tripped on o/l repeatedly, megged windings low, sent to rewind",
        asset_type="motor",
        expected=ClassificationDraft(
            category=Category.FAILURE,
            failure_mode="Motor/Electrical",
            confidence=0.88,
            evidence_span="megged windings low",
        ),
    ),
    FewShot(
        note="high vib on ODE, coupling elastomer chewed up, realigned to motor",
        asset_type="pump",
        expected=ClassificationDraft(
            category=Category.FAILURE,
            failure_mode="Coupling/Alignment",
            confidence=0.82,
            evidence_span="coupling elastomer chewed up",
        ),
    ),
    FewShot(
        note="brg housing running hot, grease starved / dried out, purged + regreased",
        asset_type="pump",
        expected=ClassificationDraft(
            category=Category.FAILURE,
            failure_mode="Lubrication",
            confidence=0.78,
            evidence_span="grease starved / dried out",
        ),
    ),
    FewShot(
        note="impeller badly eroded from cavitation, replaced impeller",
        asset_type="slurry pump",
        expected=ClassificationDraft(
            category=Category.FAILURE,
            failure_mode="Other",
            confidence=0.72,
            evidence_span="impeller badly eroded",
        ),
    ),
    FewShot(
        note="routine 3-month PM, checked alignment and lube per schedule, all ok",
        asset_type="pump",
        expected=ClassificationDraft(
            category=Category.PRECAUTIONARY,
            failure_mode=None,
            confidence=0.9,
            evidence_span="routine 3-month PM",
        ),
    ),
    FewShot(
        note="scheduled predictive vib survey, readings nominal, no action reqd",
        asset_type="pump",
        expected=ClassificationDraft(
            category=Category.PRECAUTIONARY,
            failure_mode=None,
            confidence=0.86,
            evidence_span="scheduled predictive vib survey",
        ),
    ),
    FewShot(
        note="see attached report / call day-shift supervisor",
        asset_type=None,
        expected=ClassificationDraft(
            category=Category.UNCLASSIFIABLE,
            failure_mode=None,
            confidence=0.15,
            evidence_span="",
        ),
    ),
    FewShot(
        note="checked",
        asset_type="pump",
        expected=ClassificationDraft(
            category=Category.UNCLASSIFIABLE,
            failure_mode=None,
            confidence=0.2,
            evidence_span="",
        ),
    ),
]


def render_examples(examples: list[FewShot] | None = None) -> str:
    """Render the few-shot examples as a prompt block (input -> JSON output)."""
    items = examples if examples is not None else FEW_SHOT
    blocks: list[str] = []
    for ex in items:
        asset = ex.asset_type or "unknown"
        blocks.append(
            f'Note: {ex.note}\n'
            f'Asset type: {asset}\n'
            f'Output: {ex.expected.model_dump_json()}'
        )
    return "\n\n".join(blocks)
