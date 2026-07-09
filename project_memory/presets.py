"""Ready-made `MemorySchema` presets — a preset is just a schema value.

Every preset differs only in its episode-``kind`` taxonomy (the one genuinely
project-specific knob). Copy one and edit the ``kinds`` tuple to make your own.
"""

from __future__ import annotations

from .schema import MemorySchema

# The zero-config default: a domain-neutral taxonomy for "how a project's thinking
# evolved" (decision / gotcha / insight / invariant / task / milestone / general).
GENERIC = MemorySchema()

# Tuned for an autonomous coding agent's working memory across sessions.
AGENT = MemorySchema(kinds=(
    "decision",    # a choice the agent made
    "gotcha",      # a failure it hit and how it recovered
    "insight",     # a realization worth carrying forward
    "invariant",   # a rule that must keep holding
    "todo",        # deferred work
    "observation", # something noticed about the codebase / environment
    "general",
))

# Tuned for a research / reading log.
RESEARCH = MemorySchema(kinds=(
    "finding",     # a result or claim from a source
    "question",    # an open question
    "hypothesis",  # a proposed explanation to test
    "contradiction",  # two sources disagree (a synthesis-mud candidate)
    "source",      # a pointer to a paper / doc
    "general",
))

PRESETS: dict[str, MemorySchema] = {
    "generic": GENERIC,
    "agent": AGENT,
    "research": RESEARCH,
}
