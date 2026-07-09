"""Example 03 — synthesis-mud, the epistemic guard.

`synthesize(a, b)` assesses both facts along the 5+1 axes, runs a 6-layer
compatibility check, and returns clean / bridge / refuse with a *calibrated*
confidence and a reason. It refuses to merge contradictory facts.

    python examples/03_synthesis_mud.py
"""

from project_memory import synthesize

# 1) CLEAN — two compatible observations merge freely.
clean = synthesize(
    "Most production code is read more than written.",
    "Explicit naming beats compactness for code read often.",
)
print(f"clean : {clean.verdict:6} conf={clean.confidence:.2f}  {clean.mud_reason}")

# 2) BRIDGE — a smooth principle + a rough constraint: compatible, but the merge
#    must *carry the bridge* (state both), so confidence drops. ("arguably" marks
#    fact B as rough; you can also set texture= explicitly on a Fact.)
bridge = synthesize(
    "Comprehensive test coverage is best practice for production code.",
    "Arguably, this legacy codebase is too fragile to refactor safely without tests.",
)
print(f"bridge: {bridge.verdict:6} conf={bridge.confidence:.2f}  bridging={bridge.bridging_axes}")

# 3) REFUSE (Layer 3) — opposing perspectives cannot be silently merged.
refuse = synthesize(
    "From a security perspective, storing tokens in plaintext is an unacceptable risk.",
    "From a business perspective, the plaintext token store was cheap and worked fine.",
)
print(f"refuse: {refuse.verdict:6} conf={refuse.confidence:.2f}  {refuse.mud_reason}")

# 4) REFUSE (Layer 1) — opinion is not a validated fact.
opinion = synthesize("I think Python is the best language.",
                     "Python is widely adopted in industry.")
print(f"refuse: {opinion.verdict:6} {opinion.mud_reason[:60]}")

assert clean.verdict == "clean"
assert bridge.verdict == "bridge" and "texture" in bridge.bridging_axes
assert refuse.verdict == "refuse" and refuse.is_mud
assert opinion.verdict == "refuse"
# Calibration: a clean merge is never more confident than its inputs.
assert clean.confidence <= 0.9

# ── Verify your build ────────────────────────────────────────────────────────
# You should see one clean, one bridge, and two refusals — the second refusal
# citing the security↔business perspective conflict.
print("Verify your build: ok")
