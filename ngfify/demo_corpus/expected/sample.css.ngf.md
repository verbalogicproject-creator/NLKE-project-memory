---
id: sample
kind: stylesheet
audience: engineer
status: active
owner_area: demo_corpus
main_files:
  - demo_corpus/sample.css
public_interfaces:
  - .card
  - "#header"
  - "--brand-color"
provides:
  - Demo stylesheet for ngfify's CSS deriver.
depends_on:
  - ./tokens.css
safe_edit_points:
  - "<derive: not inferable from a single file>"
risk_areas:
  - "<derive: not inferable from a single file>"
graph_rag_entities:
  - .card
  - "#header"
  - "--brand-color"
  - tokens
last_verified: __LAST_VERIFIED__
---

# sample

Demo stylesheet for ngfify's CSS deriver.

## Public interfaces

- .card
- #header
- --brand-color

> auto-declared by ngfify v0.1.1 from demo_corpus/sample.css on __GENERATED_DATE__
