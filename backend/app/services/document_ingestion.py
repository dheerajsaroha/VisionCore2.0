"""
document_ingestion.py — Enterprise Document Ingestion Pipeline
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

Handles ingestion of documents into the Knowledge Platform:
- PDF parsing and text extraction
- DOCX parsing
- Spreadsheet ingestion (CSV, XLSX)
- OCR-ready architecture
- Text chunking with configurable size/overlap
- Metadata extraction
- Chunk embedding generation
"""
from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.schema.ai import DocumentChunk, DocumentIngestionRequest, KnowledgeCollection

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """
    Enterprise document ingestion pipeline.

    Supports:
    - PDF parsing (via PyPDF2 or pdfminer)
    - DOCX parsing (via python-docx)
    - Spreadsheet ingestion (CSV, XLSX via openpyxl/csv)
    - OCR-ready architecture (Tesseract integration point)
    - Text chunking with configurable chunk size and overlap
    - Metadata extraction (title, author, date, etc.)
    """

    SUPPORTED_TYPES = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/csv": "csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "text/plain": "txt",
        "text/markdown": "md",
        "application/json": "json",
        "text/html": "html",
    }

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP = 200

    def __init__(self):
        self._supported_extractors = {
            "pdf": self._extract_pdf,
            "docx": self._extract_docx,
            "csv": self._extract_csv,
            "xlsx": self._extract_xlsx,
            "txt": self._extract_text,
            "md": self._extract_text,
            "json": self._extract_json,
            "html": self._extract_html,
        }

    async def ingest(self, request: DocumentIngestionRequest) -> list[DocumentChunk]:
        """
        Ingest a document and return text chunks.

        Steps:
        1. Validate content type and size
        2. Decode content (base64 if needed)
        3. Extract text based on content type
        4. Extract metadata
        5. Chunk text
        6. Return chunks ready for embedding
        """
        # Validate content type
        content_type = request.content_type.lower()
        doc_type = self.SUPPORTED_TYPES.get(content_type)
        if not doc_type:
            raise ValueError(f"Unsupported content type: {content_type}. Supported: {list(self.SUPPORTED_TYPES.keys())}")

        # Decode content
        content_bytes = self._decode_content(request.content)
        if len(content_bytes) > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum of {self.MAX_FILE_SIZE // (1024*1024)}MB")

        # Extract text
        extractor = self._supported_extractors.get(doc_type)
        if not extractor:
            raise ValueError(f"No extractor for document type: {doc_type}")
        text = await extractor(content_bytes, request.filename)

        if not text or not text.strip():
            raise ValueError("No text content could be extracted from the document")

        # Extract metadata
        metadata = self._extract_metadata(text, request.filename, content_type)
        if request.metadata:
            metadata.update(request.metadata)

        # Chunk text
        chunk_size = request.chunk_size or self.DEFAULT_CHUNK_SIZE
        chunk_overlap = request.chunk_overlap or self.DEFAULT_CHUNK_OVERLAP
        chunks = self._chunk_text(text, chunk_size, chunk_overlap)

        # Build document chunks
        document_id = str(uuid.uuid4())
        doc_chunks = []
        for i, chunk_text in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                text=chunk_text,
                metadata={
                    **metadata,
                    "filename": request.filename,
                    "content_type": content_type,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "total_chunks": len(chunks),
                },
                embedding=None,  # To be generated later
            )
            doc_chunks.append(chunk)

        logger.info(f"Ingested {request.filename}: {len(chunks)} chunks, {len(text)} chars")
        return doc_chunks

    # =========================================================================
    #  Text Extraction
    # =========================================================================

    async def _extract_pdf(self, content: bytes, filename: str) -> str:
        """Extract text from PDF using PyPDF2."""
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                text_parts.append(f"[Page {page_num + 1}]\n{extracted}")
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("PyPDF2 not installed, trying pdfminer")
        try:
            from pdfminer.high_level import extract_text_to_fp
            from pdfminer.layout import LAParams
            output = io.StringIO()
            with io.BytesIO(content) as fh:
                extract_text_to_fp(fh, output, laparams=LAParams(), output_type="text")
            return output.getvalue()
        except ImportError:
            raise ImportError("Either PyPDF2 or pdfminer.six is required for PDF parsing")

    async def _extract_docx(self, content: bytes, filename: str) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            # Also extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    text_parts.append(row_text)
            return "\n".join(text_parts)
        except ImportError:
            raise ImportError("python-docx is required for DOCX parsing")

    async def _extract_csv(self, content: bytes, filename: str) -> str:
        """Extract text from CSV."""
        try:
            text = content.decode("utf-8")
            reader = csv.reader(io.StringIO(text))
            lines = []
            for row in reader:
                lines.append(" | ".join(row))
            return "\n".join(lines)
        except Exception as e:
            # Fallback: return raw text
            return content.decode("utf-8", errors="replace")

    async def _extract_xlsx(self, content: bytes, filename: str) -> str:
        """Extract text from XLSX using openpyxl."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            text_parts = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                text_parts.append(f"\n[Sheet: {sheet_name}]")
                for row in ws.iter_rows(values_only=True):
                    row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
                    if row_text.strip():
                        text_parts.append(row_text)
            wb.close()
            return "\n".join(text_parts)
        except ImportError:
            raise ImportError("openpyxl is required for XLSX parsing")

    async def _extract_text(self, content: bytes, filename: str) -> str:
        """Extract text from plain text files."""
        return content.decode("utf-8", errors="replace")

    async def _extract_json(self, content: bytes, filename: str) -> str:
        """Extract text from JSON files."""
        try:
            data = json.loads(content)
            return json.dumps(data, indent=2, default=str)
        except json.JSONDecodeError:
            return content.decode("utf-8", errors="replace")

    async def _extract_html(self, content: bytes, filename: str) -> str:
        """Extract text from HTML files."""
        text = content.decode("utf-8", errors="replace")
        # Simple HTML tag removal
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # =========================================================================
    #  Metadata Extraction
    # =========================================================================

    def _extract_metadata(self, text: str, filename: str, content_type: str) -> dict:
        """Extract metadata from document content."""
        metadata = {
            "filename": filename,
            "content_type": content_type,
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.splitlines()),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        # Try to extract title from first line
        lines = text.strip().splitlines()
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 200 and not first_line.startswith(("#", "|", "-")):
                metadata["title"] = first_line[:100]

        # Check for dates
        date_pattern = r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
        dates = re.findall(date_pattern, text)
        if dates:
            metadata["detected_dates"] = dates[:10]

        return metadata

    # =========================================================================
    #  Text Chunking
    # =========================================================================

    def _chunk_text(self, text: str, chunk_size: int = 1000,
                    chunk_overlap: int = 200) -> list[str]:
        """
        Split text into overlapping chunks.

        Uses recursive splitting on paragraph, sentence, and word boundaries
        to maintain semantic coherence.
        """
        if not text:
            return []

        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        chunks = []
        start = 0

        while start < len(text):
            # Find chunk end
            end = min(start + chunk_size, len(text))

            # If not at end, try to break at paragraph or sentence boundary
            if end < len(text):
                # Try paragraph break
                paragraph_break = text.rfind("\n\n", start, end)
                if paragraph_break > start + chunk_size // 2:
                    end = paragraph_break
                else:
                    # Try sentence break
                    sentence_break = max(
                        text.rfind(". ", start, end),
                        text.rfind("! ", start, end),
                        text.rfind("? ", start, end),
                        text.rfind("\n", start, end),
                    )
                    if sentence_break > start + chunk_size // 2:
                        end = sentence_break + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - chunk_overlap if end < len(text) else len(text)

        # If no chunks produced, return whole text as single chunk
        if not chunks:
            return [text]

        return chunks

    # =========================================================================
    #  OCR Support (Architecture)
    # =========================================================================

    async def extract_with_ocr(self, image_content: bytes, filename: str) -> str:
        """
        Extract text from images using OCR.

        This is an architecture-ready hook. Requires pytesseract and Tesseract installed.
        """
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(io.BytesIO(image_content))
            text = pytesseract.image_to_string(image)
            return text
        except ImportError:
            raise ImportError("pytesseract and Pillow are required for OCR")
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise

    # =========================================================================
    #  Utilities
    # =========================================================================

    @staticmethod
    def _decode_content(content: str) -> bytes:
        """Decode content from base64 or return as bytes."""
        try:
            return base64.b64decode(content)
        except (base64.binascii.Error, ValueError):
            return content.encode("utf-8")

    def get_supported_types(self) -> dict:
        """Get supported content types."""
        return self.SUPPORTED_TYPES


# Singleton
document_ingestion_pipeline = DocumentIngestionPipeline()

