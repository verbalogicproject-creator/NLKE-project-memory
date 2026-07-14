---
id: sample
kind: code_module
audience: engineer
status: active
owner_area: demo_corpus
main_files:
  - demo_corpus/sample.ts
public_interfaces:
  - Greeting
  - greet
  - GreeterService
  - DEFAULT_NAME
  - helperAlias
provides:
  - Tiny demo module for ngfify's TypeScript deriver.
depends_on:
  - node:fs
  - ./options
  - ./helpers
safe_edit_points:
  - "<derive: not inferable from a single file>"
risk_areas:
  - "<derive: not inferable from a single file>"
graph_rag_entities:
  - Greeting
  - greet
  - GreeterService
  - DEFAULT_NAME
  - helperAlias
  - node:fs
  - options
  - helpers
last_verified: __LAST_VERIFIED__
---

# sample

Tiny demo module for ngfify's TypeScript deriver.

## Public interfaces

- Greeting
- greet
- GreeterService
- DEFAULT_NAME
- helperAlias

> auto-declared by ngfify v0.1.1 from demo_corpus/sample.ts on __GENERATED_DATE__
