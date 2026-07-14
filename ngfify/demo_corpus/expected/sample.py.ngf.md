---
id: sample
kind: code_module
audience: engineer
status: active
owner_area: demo_corpus
main_files:
  - demo_corpus/sample.py
public_interfaces:
  - greet
  - load_greeting_config
  - Greeter
provides:
  - Tiny demo module for ngfify's Python deriver.
depends_on:
  - __future__
  - json
  - pathlib
safe_edit_points:
  - "<derive: not inferable from a single file>"
risk_areas:
  - "<derive: not inferable from a single file>"
graph_rag_entities:
  - greet
  - load_greeting_config
  - Greeter
  - __future__
  - json
  - pathlib
last_verified: __LAST_VERIFIED__
---

# sample

Tiny demo module for ngfify's Python deriver.

## Public interfaces

- greet
- load_greeting_config
- Greeter

> auto-declared by ngfify v0.1.1 from demo_corpus/sample.py on __GENERATED_DATE__
