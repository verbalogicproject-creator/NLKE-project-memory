# 06 · synthesis-mud — the epistemic guard

This is the layer that makes project_memory *not just another RAG*. Most retrieval
answers *"what is similar to my query?"*. project_memory also answers *"would
merging these two facts be **clean** or **muddy**?"* — and refuses to muddy.

## The colour-theory metaphor

Mix two primary colours and you get a clean secondary: blue + yellow → green. Mix
everything and you get **MUD** — a brown that looks like a result but has lost all
coherence. Facts behave the same way. Two facts whose *qualities* clash produce a
synthesis that *looks* like progress but smuggles in one of the classic failures:

- **opinion-as-fact** — "I think Python is best" fused with "Python is widely used".
- **perspective collision** — a *security* view fused with a *business* view, as
  if one were universal.
- **certainty inflation** — a certain deduction fused with a shaky analogy, as if
  both were sure.
- **false-dichotomy inheritance**, **composition gaps**, **texture collision**.

## The 5 + 1 axes

Each fact is assessed along five aesthetic-epistemic axes, plus recursion depth:

| axis | epistemic meaning | values |
|---|---|---|
| **texture** | factual quality | `smooth` (consensus) · `rough` (contested) · `grainy` (statistical) |
| **lighting** | perspective / framing | a viewpoint: `general`, `security`, `business`, `user`, `technical`, … |
| **composition** | argument structure | `premise_conclusion` · `cause_effect` · `chronological` · `compare_contrast` · `hierarchical` · `parallel` |
| **contrast** | how difference reads | `binary` · `spectrum` · `implicit` |
| **method** | how it was reasoned | `deduction` (1.0) · `induction` (0.8) · `analogy` (0.7) · `abduction` (0.6) · `composition` |
| *(+ recursion)* | derivation depth | how many synthesis layers deep it sits |

```python
from project_memory import Fact
f = Fact.assess("From a security perspective, plaintext storage is risky.")
f.lighting     # 'security'
f.is_fact      # True
```

`Fact.assess` uses transparent marker-word rules (opinion markers → not a fact;
`%`/`most`/`often` → grainy; "from a X perspective" → that perspective; and so on).
It is a heuristic, not a model — good enough to catch the common patterns, and
every axis is **overridable** when you want precision:

```python
Fact.assess("This legacy codebase has 0% coverage.", texture="rough")
```

## The five compatibility matrices

For each axis, a small typed matrix scores how compatible two facts are `[0, 1]`.
These are ported verbatim from the methodology — e.g. texture:

```
smooth + smooth = 1.0     smooth + rough  = 0.6     smooth + grainy = 0.7
rough  + rough  = 0.8     rough  + grainy = 0.7     grainy + grainy = 0.9
```

and lighting, where **opposing perspectives** are the canonical MUD trigger:

```
same perspective              = 0.95
opposing (security↔business,  = 0.40   ← MUD
  user↔technical, ethical↔practical, performance↔security)
different but not opposing     = 0.70
```

## The 6-layer check

`detect_mud` runs six layers, cheapest first, short-circuiting on the first
failure (while still recording every axis compatibility for the audit trail):

```
Layer 1  Base       Is each input actually a fact (not opinion)?
Layer 2  Texture    Are the factual qualities compatible?
Layer 3  Lighting   Do the perspectives conflict?
Layer 4  Composition Are the argument structures compatible?
Layer 5  Contrast   Is nuance preserved (no false-dichotomy collision)?
Layer 6  Method     Are certainty levels compatible (no inflation)?

Any single axis at/below 0.4 → MUD.  Two or more axes below 0.6 → MUD.
```

## Three verdicts

`synthesize(a, b)` returns a `SynthesisResult` with one of:

| verdict | when | result |
|---|---|---|
| **clean** | all axes comfortably compatible | a merged statement; confidence ≈ the lower input certainty |
| **bridge** | compatible but frictional (some axis `< 0.7`) | a merge that *states the bridge*; lower confidence |
| **refuse** | MUD detected | no merge; `mud_reason` tells you which layer failed |

Confidence is **calibrated**: `min(certainty_a, certainty_b) × mean(compatibility)`,
lowered a further 15% for a bridge. It is *never* higher than the lower input —
synthesis can't manufacture certainty.

## Worked examples

```python
from project_memory import synthesize

# CLEAN
synthesize("Most production code is read more than written.",
           "Explicit naming beats compactness for code read often.").verdict   # 'clean'

# BRIDGE (smooth principle + rough constraint)
synthesize("Comprehensive test coverage is best practice.",
           "Arguably, this legacy codebase is too fragile to refactor without tests."
          ).verdict                                                            # 'bridge'

# REFUSE — Layer 1 (opinion is not a fact)
synthesize("I think Python is the best language.",
           "Python is widely adopted.").mud_reason        # 'Layer 1 — input A is opinion …'

# REFUSE — Layer 3 (opposing perspectives)
r = synthesize(
    "From a security perspective, plaintext tokens are an unacceptable risk.",
    "From a business perspective, plaintext tokens were cheap and worked fine.")
r.verdict        # 'refuse'
r.mud_reason     # 'Layer 3 — lighting/perspective conflict (compat=0.40)'
r.confidence     # 0.0
```

## Persisting the audit trail

Every synthesis attempt can be recorded — the `mud_detected_count` over that table
is a signal of where your system's epistemic discipline is engaging:

```python
mem.synthesize(a, b, persist=True)      # writes to the synthesis_facts table
```

## What it is *not*

It is not a neural net, not formal logic, and not a replacement for human review.
It flags *structural incompatibility patterns*; it does not prove correctness. If a
fact is mischaracterized (wrong axis), the verdict can be wrong — garbage in,
garbage out. That's why every axis is overridable.

Next: [07 · Optional dense recall](07-optional-dense.md).
