# RAG System — Next Level Roadmap

## Current State (v2)

**Pipeline:** `File → Parser → Chunker → Embeddings → SQLite → Search → Prompt`

| Component | Implementation | Status |
|-----------|---------------|--------|
| Parser | .txt, .md, .pdf, .docx, .csv/.tsv, .html, .json, .epub, source code (30+ exts) | ✅ Done |
| Chunker | Semantic (header-aware for markdown/docx) + paragraph fallback, ~2000 chars | ✅ Done |
| Embeddings | all-MiniLM-L6-v2 (384 dims, local CPU) | ✅ v1 |
| Storage | SQLite + encrypted BLOB, per-user isolation | ✅ v1 |
| Search | Cosine similarity + temporal decay (30d half-life) | ✅ v1 |
| Prompt | Top 5 chunks injected in system prompt + user message | ✅ v1 |
| Meta-tool | ingest, search, list, remove, show (5 actions) | ✅ v1 |

### What was implemented in v2:
- **Semantic chunking** (`chunker.py`): detects markdown headers, splits by section, preserves header hierarchy as context prefix in each chunk. `chunk_text_with_metadata()` returns chunks with `headers` and `section` fields.
- **More file formats** (`parser.py`): added .docx (python-docx, headings preserved as markdown), .csv/.tsv (markdown table), .html (BeautifulSoup, headings/lists → markdown), .json (pretty-print), .epub (ebooklib, chapter extraction), source code (30+ extensions with file header).
- **PDF page markers**: `[Page N]` markers for downstream section-awareness.
- **Dynamic extension validation**: meta_tool now imports `SUPPORTED_EXTENSIONS` from parser instead of hardcoding.

---

## Phase 3: Hybrid Search — BM25 + Reranking (MEDIUM PRIORITY) ✅ IMPLEMENTED

**Goal:** Combine keyword matching with semantic search for better recall.

### Changes to `documents/storage.py`:
- [ ] Add BM25 scoring alongside cosine similarity
- [ ] Implement `rank_bm25` or custom TF-IDF on chunk content
- [ ] Hybrid score: `final = α * semantic + β * bm25 + γ * decay`
- [ ] Configurable weights (default: α=0.6, β=0.25, γ=0.15)

### Optional: Cross-Encoder Reranking
- [ ] After top-20 retrieval, rerank with cross-encoder model
- [ ] Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (small, fast)
- [ ] Only rerank if `sentence-transformers` available

### Implementation Notes:
```python
# In storage.py
def search_documents(query, user_id, top_k=5, strategy="hybrid"):
    # 1. Get top-20 by semantic similarity
    semantic_results = _semantic_search(query, user_id, top_k=20)
    # 2. Get top-20 by BM25
    bm25_results = _bm25_search(query, user_id, top_k=20)
    # 3. Merge and score
    merged = _hybrid_merge(semantic_results, bm25_results, weights)
    # 4. Optional: rerank top-10 with cross-encoder
    if cross_encoder_available:
        merged = _rerank(query, merged[:10])
    return merged[:top_k]
```

### BM25 Implementation (no extra deps):
```python
import math
from collections import Counter

def _bm25_search(query: str, rows: list, top_k: int, k1=1.5, b=0.75):
    """BM25 keyword search across document chunks."""
    query_terms = query.lower().split()
    # Compute document lengths and average
    doc_lengths = [len(r[5].split()) for r in rows]  # r[5] = content
    avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1

    # IDF for each query term
    N = len(rows)
    idf = {}
    for term in query_terms:
        df = sum(1 for r in rows if term in r[5].lower())
        idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    scored = []
    for i, row in enumerate(rows):
        content_lower = row[5].lower()
        tf = Counter(content_lower.split())
        dl = doc_lengths[i]
        score = 0.0
        for term in query_terms:
            term_tf = tf.get(term, 0)
            numerator = term_tf * (k1 + 1)
            denominator = term_tf + k1 * (1 - b + b * dl / avg_dl)
            score += idf.get(term, 0) * numerator / denominator
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]
```

---

## Phase 4: Query Expansion & Multi-Hop (MEDIUM PRIORITY) ✅ IMPLEMENTED

**Goal:** Better retrieval for complex or vague queries.

### Query Expansion:
- [ ] Use Claude to expand user query into 2-3 search variants
- [ ] Example: "how does auth work?" → ["authentication flow", "JWT token handling", "login process"]
- [ ] Search each variant, deduplicate results

### Multi-Hop RAG:
- [ ] First search → extract key entities → second search on entities
- [ ] Useful for: "Compare the auth approach in the spec vs the implementation"
- [ ] Requires conversation context tracking

### Implementation in `prompt_composer.py`:
```python
async def multi_hop_search(query, user_id):
    # Hop 1: Initial search
    results_1 = search_documents(query, user_id, top_k=5)
    # Hop 2: Extract entities from results, search again
    entities = extract_key_terms(results_1)
    results_2 = search_documents(" ".join(entities), user_id, top_k=3)
    # Deduplicate and return
    return deduplicate(results_1 + results_2)
```

---

## Phase 5: Document Metadata & Collections (LOW PRIORITY) ✅ IMPLEMENTED

**Goal:** Organize documents with tags, categories, and faceted search.

### Schema changes (`documents/storage.py`):
- [ ] Add `document_meta` table: `doc_id, title, source_url, tags, category, file_type, page_count`
- [ ] Add `tags` column to document_chunks for faceted filtering
- [ ] Support search filters: `search("query", tags=["api"], file_type=".pdf")`

### Meta-tool additions (`documents/meta_tool.py`):
- [ ] `tag` action: add/remove tags to documents
- [ ] `collections` action: group documents into named collections
- [ ] `stats` action: show document count, chunk count, total size

---

## Phase 6: Advanced Embeddings (LOW PRIORITY) ✅ IMPLEMENTED

**Goal:** Pluggable embedding models for better domain coverage.

### Changes to `memories/embeddings.py`:
- [ ] Model registry: `{"default": "all-MiniLM-L6-v2", "code": "codebert-base", ...}`
- [ ] Auto-select model based on file type (code → codebert, docs → MiniLM)
- [ ] Support OpenAI embeddings API as alternative (`text-embedding-3-small`)
- [ ] Batch embedding for large documents
- [ ] Embedding cache with TTL

---

## Phase 7: Performance & Scale (LOW PRIORITY) ✅ IMPLEMENTED

**Goal:** Handle 1000+ documents without degradation.

- [ ] Replace linear SQLite scan with approximate nearest neighbor (ANN)
- [ ] Options: `faiss` (Facebook), `hnswlib`, or `sqlite-vss`
- [ ] Batch ingestion for multiple files
- [ ] Parallel chunk embedding with thread pool
- [ ] Incremental re-embedding on model change

---

## Implementation Status

| Phase | Status | Priority | Effort |
|-------|--------|----------|--------|
| 1. Semantic Chunking | ✅ Done | High | ~2h |
| 2. More Formats | ✅ Done | High | ~3h |
| 3. Hybrid Search + Reranking | ✅ Done | Medium | ~4h |
| 4. Query Expansion + Multi-Hop | ✅ Done | Medium | ~3h |
| 5. Metadata & Collections | ✅ Done | Low | ~3h |
| 6. Advanced Embeddings | ✅ Done | Low | ~4h |
| 7. Performance & Scale | ✅ Done | Low | ~5h |

---

## Files to Modify (for future phases)

- `documents/storage.py` — BM25 search, hybrid merge, metadata tables
- `documents/meta_tool.py` — New actions (tag, collections, stats)
- `memories/embeddings.py` — Model registry, batch embedding, cache
- `prompt_composer.py` — Multi-hop search, query expansion
- `pyproject.toml` — Optional deps (rank-bm25, faiss-cpu)
- `tests/test_documents.py` — Tests for new functionality