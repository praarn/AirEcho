# explanation.md — backend/app/rag/

Grounded advisory. The LLM may **only rephrase retrieved WHO / CPCB passages**,
every claim is cited, and out-of-corpus questions are refused rather than
improvised. This matters more here than elsewhere because the content is
health-adjacent.

```
rag/
├── guidelines_data.py   the bundled corpus: WHO AQG 2021 + CPCB AQI, as (section_ref, text)
├── embed.py             sentence-transformers (all-MiniLM-L6-v2, 384-d) + chunk + index
├── retrieve.py          vector search over guideline_chunks (pgvector or NumPy)
├── advisory.py          the grounded-generation pipeline + refusal + number guard
└── eval.py              tiny hand-written eval: citation-presence + correct-refusal rates
```

---

## `embed.py`

- `_model()` — lazy, process-wide `lru_cache`d `SentenceTransformer`. Tests
  monkeypatch `embed_texts` so no weights are ever downloaded.
- `embed_texts(texts)` — normalised embeddings as plain lists.
- `chunk_section(section_ref, text, max_chars=700)` — guideline sections are
  already short; only long ones are split, and each part keeps the
  `section_ref` with a `(part n)` suffix so citations stay precise.
- `index_guidelines(db, reset=True)` — idempotent rebuild of
  `guideline_documents` + `guideline_chunks` (with embeddings) from the bundled
  corpus. Run by the seed.

## `retrieve.py`

`retrieve(db, query, top_k)` → `list[RetrievedChunk(chunk_id, section_ref,
document_title, text, similarity)]`, similarity in `[-1, 1]`, higher = closer.

- **PostgreSQL:** `embedding.cosine_distance(qvec)` ordered and limited in SQL;
  `similarity = 1 - distance`.
- **SQLite (tests):** load all chunk vectors, cosine in NumPy, sort in Python.

Same contract either way, so the RAG tests exercise the real ranking logic
without Postgres.

## `advisory.py` — the pipeline

`generate_advisory(db, user_id, question, context)`:

1. `retrieve()` top-k (default 4). `top_sim = chunks[0].similarity`.
2. **Refusal gate:** if no chunks or `top_sim < settings.rag_min_score` (0.32),
   write an `advisory_log` row with `refused=True` and return `REFUSAL_TEXT`
   ("The available WHO and CPCB guidelines indexed here don't specifically
   address this…"). The LLM is never asked to improvise.
3. Otherwise build a `context_line` from the caller's current numbers (PM2.5,
   risk score, coverage) and collect `grounded_numbers` = every numeric token
   appearing in the retrieved chunks or that context line.
4. `call_llm(system, user)` — OpenAI-compatible chat completion,
   `temperature=0.2`. Returns `""` when `LLM_API_KEY` is unset or on any
   HTTP/parse error — **never raises into the request path**. The system prompt
   forbids stating any number/threshold not in the passages and requires an
   inline `[n]` after every sentence that uses one.
5. **Post-generation guards** — fall back to `_template_answer` (which only ever
   emits grounded, quoted, cited text) when: the LLM text is empty, has *no*
   `[n]` marker at all, **or** contains a number that isn't in
   `grounded_numbers` (citation markers themselves are stripped before this
   check).
6. Every retrieved passage is returned as a `citation` (`marker`, `section_ref`,
   `document_title`, `score`, `snippet`) — the reader sees the full grounding,
   not just the markers the LLM chose to type. Logged to `advisory_log`.

`context_used.used_template_renderer` tells the client whether the deterministic
path kicked in.

## `eval.py`

`python -m app.rag.eval` (needs a migrated, seeded DB). 5 grounded questions + 3
out-of-corpus questions → prints `citation_presence_rate` and
`correct_refusal_rate`. `tests/test_rag.py` mocks both the embedder and the LLM
and asserts: every non-refused answer has ≥ 1 citation; out-of-corpus questions
are refused; an LLM answer with an untraceable number is discarded for the
template renderer.
