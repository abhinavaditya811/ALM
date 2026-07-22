"""Which skill classes exist, by name. Shared by the CLI and the API layer.

v0.1 scope is ONE skill; kept as a dict (not an if/elif) so a second skill is
a one-line addition here, not a redesign of every caller.
"""

from __future__ import annotations

from skills.failure_vs_suspension.skill import FailureVsSuspensionSkill

SKILLS: dict[str, type[FailureVsSuspensionSkill]] = {
    "failure_vs_suspension": FailureVsSuspensionSkill,
}
