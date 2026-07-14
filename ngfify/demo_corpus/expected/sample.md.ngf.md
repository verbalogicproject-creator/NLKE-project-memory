---
id: sample
kind: doc
audience: engineer
status: active
owner_area: demo_corpus
main_files:
  - demo_corpus/sample.md
public_interfaces:
  - Overview
  - Details
provides:
  - This paragraph is the first one after the H1, so ngfify's Markdown deriver should pick it up verbatim as the provides value.
depends_on:
  - ./sample.py
safe_edit_points:
  - "<derive: not inferable from a single file>"
risk_areas:
  - "<derive: not inferable from a single file>"
graph_rag_entities:
  - Overview
  - Details
  - sample
last_verified: __LAST_VERIFIED__
---

# sample

This paragraph is the first one after the H1, so ngfify's Markdown deriver should pick it up verbatim as the provides value.

## Public interfaces

- Overview
- Details

> auto-declared by ngfify v0.1.1 from demo_corpus/sample.md on __GENERATED_DATE__
