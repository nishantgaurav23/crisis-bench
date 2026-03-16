# Spec S6.2 Explanation: NDMA Guidelines + SOPs Ingestion

## Why This Spec Exists

The HistoricalMemory agent (S7.8) needs to ground its responses in real NDMA disaster management procedures — not hallucinated ones. Without ingested NDMA documents, the RAG pipeline from S6.1 has no knowledge base to query. This spec fills those ChromaDB collections with actual NDMA guidelines, SOPs, state SDMA reports, and annual reports.

The requirement comes from FR-007.1: "RAG knowledge base over NDMA guidelines (30+ PDFs: flood management, cyclone, earthquake, heatwave, chemical disaster, urban flooding SOPs), state SDMA reports, NDMA annual reports."

## What It Does

1. **PDF Text Extraction** — Uses PyMuPDF (`fitz`) to extract text from NDMA PDF files, preserving per-page boundaries and metadata.

2. **Document Classification** — Categorizes PDFs into 4 types based on filename patterns:
   - `guidelines` → `ndma_guidelines` collection
   - `sops` → `ndma_sops` collection
   - `sdma_reports` → `state_sdma_reports` collection
   - `annual_reports` → `ndma_annual` collection

3. **Metadata Enrichment** — Attaches structured metadata to every chunk:
   - `disaster_type`: flood, cyclone, earthquake, heatwave, chemical, landslide, urban_flooding, tsunami, general
   - `state`: For SDMA reports, extracts the Indian state (28 states + 3 UTs supported)
   - `page_number`, `source_filename`, `document_id` (SHA-256 hash of filename)

4. **Batch Ingestion** — `NDMAIngestionPipeline` processes individual files or entire directories, with graceful error handling (one corrupt file doesn't abort the batch).

5. **Deduplication** — Delegates to `EmbeddingPipeline.embed_and_store()` which uses `document_id`-based dedup to prevent re-processing.

## How It Works

```
PDF file(s)
    │
    ▼
extract_text_from_pdf()  ─── PyMuPDF fitz.open() → per-page text
    │
    ▼
classify_document()      ─── filename pattern matching → category
infer_disaster_type()    ─── filename pattern matching → disaster type
extract_state_name()     ─── filename matching against 28+3 Indian states
    │
    ▼
NDMAIngestionPipeline.ingest_file()
    │
    ├── Build metadata per page
    ├── Filter empty pages
    └── Call EmbeddingPipeline.embed_and_store()
         │
         ├── TextChunker.chunk()     ─── 512-char chunks, 64-char overlap
         ├── OllamaEmbedder.embed()  ─── nomic-embed-text → 768-dim vectors
         └── ChromaDB collection.add()
```

## Key Design Decisions

- **PyMuPDF over pdfminer/pdfplumber**: PyMuPDF is already a dependency, handles multi-column layouts well, and is the fastest Python PDF parser. No additional dependency needed.
- **Filename-based classification**: NDMA PDFs follow predictable naming conventions. This avoids the cost/complexity of content-based classification while being accurate enough for the 4 categories.
- **SHA-256 document IDs**: Deterministic from filename, enabling re-runnable ingestion without duplicates.
- **Graceful batch error handling**: `IngestionReport` tracks errors per file, so the operator knows which PDFs need attention without losing progress on the rest.

## Connections

| Direction | Spec | Relationship |
|-----------|------|-------------|
| Depends on | S6.1 (ChromaDB Setup) | Uses `EmbeddingPipeline`, `TextChunker`, `ChromaDBManager`, collection registry |
| Depended by | S7.8 (HistoricalMemory Agent) | Queries `ndma_guidelines` and `ndma_sops` collections for RAG |
| Depended by | S6.6 (Scenario Generator) | Uses NDMA guidelines to validate generated scenarios |
| Related | S5.2 (MCP SACHET) | SACHET provides real-time alerts; NDMA docs provide the procedures to follow |

## Interview Q&A

**Q: Why chunk at 512 characters with 64-char overlap instead of using full pages?**
A: LLM context windows are limited and expensive. Retrieving a full 3000-char page when only 200 chars are relevant wastes tokens and dilutes the signal. 512-char chunks with overlap ensure: (1) retrieved context is focused, (2) sentence boundaries aren't broken across chunks, (3) the RAG system can find specific procedures (e.g., "cyclone T+12h evacuation steps") without returning entire chapters.

**Q: How do you handle scanned PDFs (images without OCR)?**
A: We detect empty pages (no extractable text) and skip them. For a production system, we'd add OCR via Tesseract or the Qwen VL vision model, but that's out of scope for this spec. The majority of NDMA documents are text-based PDFs, so this handles ~95% of cases.

**Q: Why not use LangChain's document loaders?**
A: LangChain's `PyPDFLoader` adds an unnecessary abstraction layer over PyMuPDF with no benefit for our use case. We need page-level metadata, filename-based classification, and custom chunking — all of which require custom logic anyway. Direct PyMuPDF usage is simpler, faster, and has zero additional dependencies.
