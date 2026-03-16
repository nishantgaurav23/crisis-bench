# Spec S6.2: NDMA Guidelines + SOPs Ingestion

**Phase**: 6 — Data Pipeline
**Location**: `src/data/ingest/ndma_pdfs.py`
**Depends On**: S6.1 (ChromaDB Setup + Embedding Pipeline)
**Status**: pending

---

## Overview

Ingest NDMA (National Disaster Management Authority) guidelines, SOPs, state SDMA reports, and annual reports into ChromaDB for RAG retrieval. This module parses PDF documents, extracts text with page-level metadata, chunks the text, and stores embeddings in the appropriate ChromaDB collections. The HistoricalMemory agent (S7.8) depends on this for grounding LLM responses in real NDMA procedures.

## Requirements

### R1: PDF Text Extraction
- Extract text from PDF files using PyMuPDF (`fitz`)
- Preserve page-level metadata (page number, total pages)
- Handle multi-column layouts, tables, and headers/footers gracefully
- Skip pages with no extractable text (scanned images without OCR)
- Return structured `PDFDocument` Pydantic model with per-page text

### R2: Document Classification
- Classify NDMA documents into categories based on filename/metadata:
  - `guidelines` — Main NDMA guideline PDFs (flood, cyclone, earthquake, heatwave, chemical, urban flooding)
  - `sops` — Standard Operating Procedures per disaster type
  - `sdma_reports` — State SDMA after-action reports
  - `annual_reports` — NDMA annual reports
- Map each category to its corresponding ChromaDB collection from the registry

### R3: Metadata Enrichment
- Extract metadata from each document:
  - `document_id`: Unique identifier (filename hash or provided ID)
  - `source_filename`: Original PDF filename
  - `disaster_type`: Inferred from filename/content (flood, cyclone, earthquake, heatwave, chemical, landslide, urban_flooding, general)
  - `category`: guidelines | sops | sdma_reports | annual_reports
  - `page_number`: Page within the PDF
  - `total_pages`: Total pages in the PDF
  - `state`: For SDMA reports, the state name (e.g., "Odisha", "Kerala")
- Attach metadata to every chunk before embedding

### R4: Ingestion Pipeline
- `NDMAIngestionPipeline` class that:
  1. Scans a directory for PDF files
  2. Extracts text from each PDF (via PyMuPDF)
  3. Classifies the document into a category
  4. Enriches metadata per page
  5. Calls `EmbeddingPipeline.embed_and_store()` to chunk, embed, and store
- Supports processing a single file or a batch directory
- Returns an `IngestionReport` with counts: files processed, chunks stored, files skipped (duplicates), errors

### R5: Deduplication
- Leverage the existing `document_id`-based deduplication in `EmbeddingPipeline`
- Use filename-based document IDs so re-running ingestion skips already-processed files

### R6: Error Handling
- Raise `DataError` for unreadable/corrupt PDFs
- Log and skip individual file errors without aborting the batch
- Track errors in the `IngestionReport`

## Outcomes

1. PDF text extracted with per-page metadata using PyMuPDF
2. Documents classified into 4 categories and routed to correct ChromaDB collections
3. Metadata enriched with disaster type, state, page number
4. Batch ingestion with directory scanning
5. Deduplication prevents re-processing
6. Errors logged and reported without batch abort

## TDD Notes

### Test Cases
- `test_pdf_document_model` — PDFDocument Pydantic model creation and validation
- `test_extract_text_from_pdf` — mock PyMuPDF, verify per-page text extraction
- `test_extract_text_empty_page` — pages with no text are handled (empty string)
- `test_extract_text_corrupt_pdf` — raises DataError for unreadable files
- `test_classify_document_guidelines` — "flood_management_guidelines.pdf" → guidelines
- `test_classify_document_sops` — "cyclone_sop.pdf" → sops
- `test_classify_document_sdma` — "odisha_sdma_report.pdf" → sdma_reports
- `test_classify_document_annual` — "ndma_annual_report_2023.pdf" → annual_reports
- `test_classify_document_default` — unknown patterns default to guidelines
- `test_metadata_enrichment` — disaster type inferred, state extracted for SDMA
- `test_category_to_collection_mapping` — each category maps to correct ChromaDB collection
- `test_ingest_single_file` — end-to-end: PDF → extract → classify → enrich → embed → store
- `test_ingest_directory` — batch processing of multiple PDFs
- `test_ingest_deduplication` — re-ingesting same file skips it
- `test_ingest_report` — IngestionReport counts are accurate
- `test_ingest_partial_failure` — one bad file doesn't abort the batch

### Mocking Strategy
- Mock `fitz.open()` (PyMuPDF) for PDF extraction
- Mock `EmbeddingPipeline.embed_and_store()` for storage
- Mock filesystem operations (`pathlib.Path.glob`) for directory scanning
- Never hit real filesystem, ChromaDB, or Ollama in tests
