# Advisor RAG Corpus

Curated security-control snippets used by the Anthropic remediation provider
as grounding context. Each file maps to one or more `CFN_*_NNN` rule ids via
its frontmatter-style header.

This corpus is intentionally small and lexical: the retriever scores
passages by `rule_id` exact match plus keyword overlap (resource type,
message tokens). No embeddings, no vector store. Determinism beats recall
for an MVP — and the prompt already constrains the model to ground its
output in retrieved context.

**Production swap:** replace the lexical retriever with an embedding-backed
vector index (e.g. `sentence-transformers` + `qdrant`/`pgvector`) keyed on
the same passage IDs. Keep the in-repo corpus as the source of truth.
