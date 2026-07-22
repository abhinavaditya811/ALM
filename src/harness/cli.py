"""CLI entrypoint: score a skill against its frozen eval set with a real backend.

Design constraints (see CLAUDE.md / docs/architecture.md):
- This is the composition root for a scoring RUN: the one place a real
  `ModelBackend` gets wired into the otherwise-pure scoring machinery.
  `harness.scoring.score_skill` itself stays pure; this module owns all the
  I/O and LLM calls that a real run requires.
- Invoked via `python -m harness.scoring --skill <name>` (see the `__main__`
  guard at the bottom of `scoring.py`), so this module can also be imported
  and used directly in tests without a subprocess.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from harness.evalset import load_eval_set
from harness.scoring import score_skill
from llm.client import ModelBackend
from llm.registry import BACKENDS
from schema.models import Classification, SkillScore
from skills.registry import SKILLS


def run_scoring(
    skill_name: str, backend: ModelBackend, eval_set_path: Path | None = None
) -> SkillScore:
    """Run `skill_name` over the frozen eval set with `backend` and score it.

    Takes an already-constructed `backend` (rather than building one itself)
    so this is directly unit-testable with a fake, the same pattern
    `tests/test_harness_loop.py` uses for the end-to-end loop test.
    """
    try:
        skill_cls = SKILLS[skill_name]
    except KeyError:
        raise SystemExit(
            f"unknown skill: {skill_name!r} (choices: {sorted(SKILLS)})"
        ) from None

    eval_cases = load_eval_set(eval_set_path)
    skill = skill_cls(backend=backend)
    classifications: list[Classification] = [skill.run(case.record) for case in eval_cases]
    return score_skill(
        classifications,
        eval_cases,
        skill_version=skill.version,
        run_id=uuid.uuid4().hex[:12],
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score a skill against its frozen eval set.")
    parser.add_argument("--skill", required=True, choices=sorted(SKILLS))
    parser.add_argument("--backend", default="deepseek", choices=sorted(BACKENDS))
    args = parser.parse_args(argv)

    backend_cls = BACKENDS[args.backend]
    score = run_scoring(args.skill, backend_cls())
    print(score.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
