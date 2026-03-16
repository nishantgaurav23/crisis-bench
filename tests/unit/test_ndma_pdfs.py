"""Tests for NDMA guidelines + SOPs ingestion (S6.2).

Tests cover: PDF text extraction, document classification, metadata enrichment,
single-file ingestion, batch directory ingestion, deduplication, error handling.
All external services (PyMuPDF, ChromaDB, Ollama, filesystem) are mocked.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.ingest.ndma_pdfs import (
    CATEGORY_COLLECTION_MAP,
    DISASTER_TYPE_PATTERNS,
    IngestionReport,
    NDMAIngestionPipeline,
    PDFDocument,
    PDFPage,
    classify_document,
    extract_state_name,
    extract_text_from_pdf,
    infer_disaster_type,
)
from src.shared.errors import DataError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_embedding_pipeline():
    """Mock EmbeddingPipeline for storage."""
    pipeline = AsyncMock()
    pipeline.embed_and_store = AsyncMock(return_value=10)
    return pipeline


@pytest.fixture
def ingestion_pipeline(mock_embedding_pipeline):
    """NDMAIngestionPipeline with mocked embedding pipeline."""
    return NDMAIngestionPipeline(embedding_pipeline=mock_embedding_pipeline)


def _make_mock_page(text: str, page_num: int = 0) -> MagicMock:
    """Create a mock fitz page with given text."""
    page = MagicMock()
    page.get_text.return_value = text
    page.number = page_num
    return page


def _make_mock_pdf(pages: list[str]) -> MagicMock:
    """Create a mock fitz.Document with given page texts."""
    doc = MagicMock()
    doc.page_count = len(pages)
    mock_pages = [_make_mock_page(text, i) for i, text in enumerate(pages)]
    doc.__iter__ = MagicMock(return_value=iter(mock_pages))
    doc.__len__ = MagicMock(return_value=len(pages))
    doc.close = MagicMock()
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    return doc


# =============================================================================
# Pydantic Models
# =============================================================================


class TestPDFPage:
    def test_pdf_page_creation(self):
        page = PDFPage(text="Some text", page_number=1, total_pages=5)
        assert page.text == "Some text"
        assert page.page_number == 1
        assert page.total_pages == 5

    def test_pdf_page_empty_text_allowed(self):
        """Empty pages (scanned images) are represented with empty text."""
        page = PDFPage(text="", page_number=0, total_pages=1)
        assert page.text == ""


class TestPDFDocument:
    def test_pdf_document_creation(self):
        pages = [PDFPage(text="Page 1 text", page_number=0, total_pages=2)]
        doc = PDFDocument(
            filename="flood_guidelines.pdf",
            pages=pages,
            total_pages=2,
        )
        assert doc.filename == "flood_guidelines.pdf"
        assert len(doc.pages) == 1
        assert doc.total_pages == 2

    def test_pdf_document_full_text(self):
        """full_text property concatenates all page texts."""
        pages = [
            PDFPage(text="Page one.", page_number=0, total_pages=2),
            PDFPage(text="Page two.", page_number=1, total_pages=2),
        ]
        doc = PDFDocument(filename="test.pdf", pages=pages, total_pages=2)
        assert "Page one." in doc.full_text
        assert "Page two." in doc.full_text

    def test_pdf_document_text_pages_only(self):
        """text_pages property returns only pages with non-empty text."""
        pages = [
            PDFPage(text="Has text.", page_number=0, total_pages=3),
            PDFPage(text="", page_number=1, total_pages=3),
            PDFPage(text="Also text.", page_number=2, total_pages=3),
        ]
        doc = PDFDocument(filename="test.pdf", pages=pages, total_pages=3)
        assert len(doc.text_pages) == 2


class TestIngestionReport:
    def test_ingestion_report_creation(self):
        report = IngestionReport(
            files_processed=5,
            chunks_stored=100,
            files_skipped=1,
            errors=[],
        )
        assert report.files_processed == 5
        assert report.chunks_stored == 100
        assert report.files_skipped == 1
        assert len(report.errors) == 0

    def test_ingestion_report_with_errors(self):
        report = IngestionReport(
            files_processed=3,
            chunks_stored=50,
            files_skipped=0,
            errors=["corrupt.pdf: Failed to parse"],
        )
        assert len(report.errors) == 1


# =============================================================================
# PDF Text Extraction
# =============================================================================


class TestExtractTextFromPDF:
    def test_extract_text_from_pdf(self):
        """Extract text from a mock PDF with multiple pages."""
        mock_doc = _make_mock_pdf(["Page 1 content.", "Page 2 content."])

        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = extract_text_from_pdf(Path("/fake/flood_guidelines.pdf"))

        assert isinstance(result, PDFDocument)
        assert result.filename == "flood_guidelines.pdf"
        assert result.total_pages == 2
        assert len(result.pages) == 2
        assert result.pages[0].text == "Page 1 content."

    def test_extract_text_empty_page(self):
        """Pages with no text return empty string (not skipped)."""
        mock_doc = _make_mock_pdf(["Content.", "", "More content."])

        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = extract_text_from_pdf(Path("/fake/test.pdf"))

        assert result.total_pages == 3
        assert len(result.pages) == 3
        assert result.pages[1].text == ""

    def test_extract_text_corrupt_pdf(self):
        """Raises DataError for unreadable PDF files."""
        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.side_effect = Exception("Cannot open file")

            with pytest.raises(DataError, match="Failed to parse PDF"):
                extract_text_from_pdf(Path("/fake/corrupt.pdf"))


# =============================================================================
# Document Classification
# =============================================================================


class TestClassifyDocument:
    def test_classify_guidelines(self):
        assert classify_document("flood_management_guidelines.pdf") == "guidelines"

    def test_classify_guidelines_variant(self):
        assert classify_document("ndma_earthquake_guideline.pdf") == "guidelines"

    def test_classify_sops(self):
        assert classify_document("cyclone_sop.pdf") == "sops"

    def test_classify_sops_variant(self):
        assert classify_document("standard_operating_procedure_flood.pdf") == "sops"

    def test_classify_sdma_reports(self):
        assert classify_document("odisha_sdma_report_2023.pdf") == "sdma_reports"

    def test_classify_sdma_variant(self):
        assert classify_document("kerala_sdma_after_action.pdf") == "sdma_reports"

    def test_classify_annual_reports(self):
        assert classify_document("ndma_annual_report_2023.pdf") == "annual_reports"

    def test_classify_annual_variant(self):
        assert classify_document("annual_report_2022_23.pdf") == "annual_reports"

    def test_classify_default_guidelines(self):
        """Unknown patterns default to guidelines."""
        assert classify_document("random_document.pdf") == "guidelines"


# =============================================================================
# Disaster Type Inference
# =============================================================================


class TestInferDisasterType:
    def test_infer_flood(self):
        assert infer_disaster_type("flood_management_guidelines.pdf") == "flood"

    def test_infer_cyclone(self):
        assert infer_disaster_type("cyclone_preparedness_sop.pdf") == "cyclone"

    def test_infer_earthquake(self):
        assert infer_disaster_type("earthquake_response_guide.pdf") == "earthquake"

    def test_infer_heatwave(self):
        assert infer_disaster_type("heat_wave_action_plan.pdf") == "heatwave"

    def test_infer_chemical(self):
        assert infer_disaster_type("chemical_disaster_management.pdf") == "chemical"

    def test_infer_landslide(self):
        assert infer_disaster_type("landslide_risk_assessment.pdf") == "landslide"

    def test_infer_urban_flooding(self):
        assert infer_disaster_type("urban_flooding_guidelines.pdf") == "urban_flooding"

    def test_infer_tsunami(self):
        assert infer_disaster_type("tsunami_warning_sop.pdf") == "tsunami"

    def test_infer_general(self):
        """Unknown disaster type defaults to general."""
        assert infer_disaster_type("random_document.pdf") == "general"


# =============================================================================
# State Name Extraction
# =============================================================================


class TestExtractStateName:
    def test_extract_odisha(self):
        assert extract_state_name("odisha_sdma_report.pdf") == "Odisha"

    def test_extract_kerala(self):
        assert extract_state_name("kerala_sdma_after_action.pdf") == "Kerala"

    def test_extract_tamil_nadu(self):
        assert extract_state_name("tamil_nadu_sdma_report.pdf") == "Tamil Nadu"

    def test_extract_west_bengal(self):
        assert extract_state_name("west_bengal_sdma_2023.pdf") == "West Bengal"

    def test_extract_no_state(self):
        """Returns None if no state is found."""
        assert extract_state_name("ndma_flood_guidelines.pdf") is None


# =============================================================================
# Category to Collection Mapping
# =============================================================================


class TestCategoryCollectionMap:
    def test_guidelines_maps_to_ndma_guidelines(self):
        assert CATEGORY_COLLECTION_MAP["guidelines"] == "ndma_guidelines"

    def test_sops_maps_to_ndma_sops(self):
        assert CATEGORY_COLLECTION_MAP["sops"] == "ndma_sops"

    def test_sdma_maps_to_state_sdma_reports(self):
        assert CATEGORY_COLLECTION_MAP["sdma_reports"] == "state_sdma_reports"

    def test_annual_maps_to_ndma_annual(self):
        assert CATEGORY_COLLECTION_MAP["annual_reports"] == "ndma_annual"


# =============================================================================
# NDMAIngestionPipeline — Single File
# =============================================================================


class TestIngestSingleFile:
    async def test_ingest_single_file(self, ingestion_pipeline, mock_embedding_pipeline):
        """End-to-end: PDF → extract → classify → enrich → embed → store."""
        mock_doc = _make_mock_pdf(["Flood management procedures.", "Evacuation protocol."])

        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            report = await ingestion_pipeline.ingest_file(
                Path("/fake/flood_management_guidelines.pdf")
            )

        assert report.files_processed == 1
        assert report.chunks_stored == 10  # mocked return value
        assert report.files_skipped == 0
        assert len(report.errors) == 0
        mock_embedding_pipeline.embed_and_store.assert_called_once()

        # Verify correct collection was used
        call_args = mock_embedding_pipeline.embed_and_store.call_args
        assert call_args[1]["collection_name"] == "ndma_guidelines" or (
            call_args[0][0] == "ndma_guidelines"
        )

    async def test_ingest_single_file_with_metadata(
        self, ingestion_pipeline, mock_embedding_pipeline
    ):
        """Metadata includes disaster type and source filename."""
        mock_doc = _make_mock_pdf(["Cyclone preparedness."])

        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            await ingestion_pipeline.ingest_file(Path("/fake/cyclone_sop.pdf"))

        call_args = mock_embedding_pipeline.embed_and_store.call_args
        metadatas = call_args[1].get("metadatas") or call_args[0][2]
        assert any(m.get("disaster_type") == "cyclone" for m in metadatas)
        assert any(m.get("source_filename") == "cyclone_sop.pdf" for m in metadatas)

    async def test_ingest_corrupt_file(self, ingestion_pipeline):
        """Corrupt PDF returns report with error, doesn't raise."""
        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.side_effect = Exception("Cannot open file")
            report = await ingestion_pipeline.ingest_file(Path("/fake/corrupt.pdf"))

        assert report.files_processed == 0
        assert report.chunks_stored == 0
        assert len(report.errors) == 1
        assert "corrupt.pdf" in report.errors[0]


# =============================================================================
# NDMAIngestionPipeline — Directory
# =============================================================================


class TestIngestDirectory:
    async def test_ingest_directory(self, ingestion_pipeline, mock_embedding_pipeline):
        """Batch processing of multiple PDFs from a directory."""
        pdf_files = [
            Path("/fake/dir/flood_guidelines.pdf"),
            Path("/fake/dir/cyclone_sop.pdf"),
            Path("/fake/dir/earthquake_guide.pdf"),
        ]

        with (
            patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz,
            patch("pathlib.Path.glob", return_value=pdf_files),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            mock_fitz.open.side_effect = lambda _: _make_mock_pdf(["Some content."])
            report = await ingestion_pipeline.ingest_directory(Path("/fake/dir"))

        assert report.files_processed == 3
        assert report.chunks_stored == 30  # 10 per file (mocked)
        assert mock_embedding_pipeline.embed_and_store.call_count == 3

    async def test_ingest_directory_partial_failure(
        self, ingestion_pipeline, mock_embedding_pipeline
    ):
        """One bad file doesn't abort the batch."""
        pdf_files = [
            Path("/fake/dir/good1.pdf"),
            Path("/fake/dir/corrupt.pdf"),
            Path("/fake/dir/good2.pdf"),
        ]

        def open_side_effect(path):
            path_str = str(path)
            if "corrupt" in path_str:
                raise Exception("Cannot open file")
            return _make_mock_pdf(["Good content."])

        with (
            patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz,
            patch("pathlib.Path.glob", return_value=pdf_files),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            mock_fitz.open.side_effect = open_side_effect
            report = await ingestion_pipeline.ingest_directory(Path("/fake/dir"))

        assert report.files_processed == 2
        assert report.chunks_stored == 20  # 10 per good file
        assert len(report.errors) == 1
        assert "corrupt.pdf" in report.errors[0]

    async def test_ingest_directory_not_found(self, ingestion_pipeline):
        """Non-existent directory raises DataError."""
        with patch("pathlib.Path.is_dir", return_value=False):
            with pytest.raises(DataError, match="not a valid directory"):
                await ingestion_pipeline.ingest_directory(Path("/nonexistent"))

    async def test_ingest_directory_empty(self, ingestion_pipeline):
        """Empty directory returns zero counts."""
        with (
            patch("pathlib.Path.glob", return_value=[]),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            report = await ingestion_pipeline.ingest_directory(Path("/empty/dir"))

        assert report.files_processed == 0
        assert report.chunks_stored == 0


# =============================================================================
# Deduplication
# =============================================================================


class TestDeduplication:
    async def test_deduplication_via_document_id(self, ingestion_pipeline, mock_embedding_pipeline):
        """Deduplication is handled by EmbeddingPipeline — we verify document_id is passed."""
        mock_doc = _make_mock_pdf(["Content."])

        with patch("src.data.ingest.ndma_pdfs.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            await ingestion_pipeline.ingest_file(Path("/fake/flood_guidelines.pdf"))

        call_args = mock_embedding_pipeline.embed_and_store.call_args
        metadatas = call_args[1].get("metadatas") or call_args[0][2]
        # Every metadata dict should have a document_id for deduplication
        assert all("document_id" in m for m in metadatas)


# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    def test_disaster_type_patterns_exist(self):
        """DISASTER_TYPE_PATTERNS has entries for key disaster types."""
        assert "flood" in DISASTER_TYPE_PATTERNS
        assert "cyclone" in DISASTER_TYPE_PATTERNS
        assert "earthquake" in DISASTER_TYPE_PATTERNS

    def test_category_collection_map_complete(self):
        """All 4 categories mapped."""
        assert len(CATEGORY_COLLECTION_MAP) == 4
