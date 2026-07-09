# 07 · Optional dense recall

Dense (semantic) recall is a **booster, never a dependency**. With no embedder,
project_memory runs pure lexical (BM25 + structural + intent fusion) and is
byte-for-byte deterministic. Add an embedder and it fuses a fourth,
cosine-similarity signal for paraphrase recall — matches that share *meaning* but
few words.

## The degradation contract

It degrades cleanly in every failure mode — the same contract across the whole
family:

| situation | result |
|---|---|
| no embedder passed | pure lexical (byte-identical determinism) |
| `numpy` not installed | pure lexical (install `[dense]` to enable) |
| embedder returns `None` (server down) | pure lexical |

There is a test that asserts a **dead embedder returns byte-identical results to
no embedder** (`test_dense.py::test_dead_embedder_is_byte_identical_to_no_dense`).

## Bring your own embedder

An embedder is any `str -> Sequence[float] | None` callable:

```python
from project_memory import ProjectMemory

def my_embed(text: str):
    return model.encode(text).tolist()   # or return None on failure

mem = ProjectMemory.open("memory.db", embedder=my_embed)
```

The index embeds each row's *surface* — an episode's content + kind + tags, or a
fact's claim + reason + tags — and rebuilds automatically whenever you write.

## A ready-made local embedder

`http_embedder()` targets an OpenAI-style `/v1/embeddings` endpoint (llama.cpp,
Ollama, …), stdlib-only, returning `None` on any failure:

```python
from project_memory import http_embedder
mem = ProjectMemory.open("memory.db",
                         embedder=http_embedder("http://127.0.0.1:8140/v1/embeddings"))
```

Configurable via args or env: `PMEM_EMBED_URL`, `PMEM_EMBED_MODEL`,
`PMEM_EMBED_QUERY_PREFIX`.

## A deterministic embedder for tests

`hash_embedder()` is a deterministic bag-of-words embedder (no model, no network)
— it lets you *exercise* the dense path offline (paraphrases with shared words land
nearby). It's not semantic, but it's real in the interface sense:

```python
from project_memory import build_demo, hash_embedder
mem = build_demo(embedder=hash_embedder())
```

## Installing the extra

```bash
pip install -e ".[dense]"     # adds numpy (via declared-core[dense])
```

`dense_available()` tells you whether numpy is importable. Without it,
`build_dense_index` returns `None` and recall stays lexical.

Next: [08 · API reference](08-api-reference.md).
