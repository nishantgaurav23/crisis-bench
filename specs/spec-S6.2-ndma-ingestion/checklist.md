# Spec S6.2 Implementation Checklist

## Phase 1: RED — Write Failing Tests
- [x] Create `tests/unit/test_ndma_pdfs.py`
- [x] Write tests for Pydantic models (`PDFDocument`, `PDFPage`, `IngestionReport`)
- [x] Write tests for PDF text extraction (mock PyMuPDF)
- [x] Write tests for document classification
- [x] Write tests for metadata enrichment (disaster type, state name)
- [x] Write tests for single-file ingestion
- [x] Write tests for batch directory ingestion
- [x] Write tests for deduplication
- [x] Write tests for error handling (corrupt PDF, partial failure)
- [x] Verify all tests FAIL (no implementation yet)

## Phase 2: GREEN — Implement Minimum Code
- [x] Create `src/data/ingest/ndma_pdfs.py`
- [x] Implement `PDFPage`, `PDFDocument`, and `IngestionReport` Pydantic models
- [x] Implement `extract_text_from_pdf()` using PyMuPDF
- [x] Implement `classify_document()` with filename pattern matching
- [x] Implement `infer_disaster_type()` from filename
- [x] Implement `extract_state_name()` for SDMA reports
- [x] Implement `NDMAIngestionPipeline` class
- [x] Implement `ingest_file()` method
- [x] Implement `ingest_directory()` method
- [x] Verify all tests PASS (47 passing)

## Phase 3: REFACTOR — Clean Up
- [x] Run `ruff check` and fix lint issues (import sorting)
- [x] Run `ruff format` to ensure formatting
- [x] Verify all tests still pass (72 total: 47 S6.2 + 25 S6.1)
