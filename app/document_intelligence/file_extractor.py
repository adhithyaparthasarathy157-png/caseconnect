"""
File text and metadata extractor for uploaded complaint evidence documents.
Supports PDF (via pypdf), images (via PIL), and text files.
Detects corrupted, empty, or unreadable files.
"""
from __future__ import annotations

import io
import logging
from typing import Any

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)


class ExtractedFileContent:
    def __init__(
        self,
        filename: str,
        content_type: str,
        text: str,
        page_count: int = 1,
        is_readable: bool = True,
        is_corrupted: bool = False,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.text = text
        self.page_count = page_count
        self.is_readable = is_readable
        self.is_corrupted = is_corrupted
        self.error_message = error_message
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "text_length": len(self.text),
            "text_snippet": self.text[:200] if self.text else "",
            "page_count": self.page_count,
            "is_readable": self.is_readable,
            "is_corrupted": self.is_corrupted,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


def extract_content_from_file_bytes(
    file_bytes: bytes,
    filename: str,
    content_type: str | None = None,
) -> ExtractedFileContent:
    """
    Extracts text and validates format from uploaded file bytes.
    Handles PDF, images (PNG, JPEG, etc.), and plain text.
    Catches corruption and unreadable files.
    """
    if not file_bytes or len(file_bytes.strip()) == 0:
        return ExtractedFileContent(
            filename=filename,
            content_type=content_type or "application/octet-stream",
            text="",
            is_readable=False,
            is_corrupted=True,
            error_message="Uploaded file is empty (0 bytes).",
        )

    fn_lower = filename.lower()
    ct_lower = (content_type or "").lower()

    # 1. Plain text / CSV / Markdown
    if fn_lower.endswith((".txt", ".csv", ".json", ".md")) or "text/" in ct_lower:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as e:
                return ExtractedFileContent(
                    filename=filename,
                    content_type=content_type or "text/plain",
                    text="",
                    is_readable=False,
                    is_corrupted=True,
                    error_message=f"Unable to decode text file: {e}",
                )

        if not text.strip():
            return ExtractedFileContent(
                filename=filename,
                content_type=content_type or "text/plain",
                text="",
                is_readable=False,
                error_message="Text document contains no readable text content.",
            )

        return ExtractedFileContent(
            filename=filename,
            content_type=content_type or "text/plain",
            text=text.strip(),
            page_count=1,
            is_readable=True,
            metadata={"encoding": "utf-8", "char_count": len(text)},
        )

    # 2. PDF Document
    if fn_lower.endswith(".pdf") or "pdf" in ct_lower:
        try:
            stream = io.BytesIO(file_bytes)
            reader = PdfReader(stream)

            if reader.is_encrypted:
                try:
                    # Attempt empty password decrypt
                    reader.decrypt("")
                except Exception:
                    return ExtractedFileContent(
                        filename=filename,
                        content_type="application/pdf",
                        text="",
                        page_count=len(reader.pages) if reader.pages else 0,
                        is_readable=False,
                        is_corrupted=False,
                        error_message="PDF document is password-protected or encrypted.",
                    )

            pages_text: list[str] = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text.strip())

            full_text = "\n\n".join(pages_text).strip()
            num_pages = len(reader.pages)

            if not full_text:
                return ExtractedFileContent(
                    filename=filename,
                    content_type="application/pdf",
                    text="",
                    page_count=num_pages,
                    is_readable=False,
                    is_corrupted=False,
                    error_message="PDF contains no extractable text stream (possible scanned image without OCR layer).",
                    metadata={"page_count": num_pages},
                )

            return ExtractedFileContent(
                filename=filename,
                content_type="application/pdf",
                text=full_text,
                page_count=num_pages,
                is_readable=True,
                metadata={
                    "page_count": num_pages,
                    "pdf_info": {k: str(v) for k, v in (reader.metadata or {}).items()},
                },
            )

        except (PdfReadError, Exception) as exc:
            logger.warning("PDF reading error for %s: %s", filename, exc)
            return ExtractedFileContent(
                filename=filename,
                content_type="application/pdf",
                text="",
                is_readable=False,
                is_corrupted=True,
                error_message=f"PDF file is damaged or corrupted: {exc}",
            )

    # 3. Image Document (PNG, JPG, TIFF, etc.)
    if fn_lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")) or "image/" in ct_lower:
        try:
            stream = io.BytesIO(file_bytes)
            img = Image.open(stream)
            img.verify()  # Validate image integrity

            # Reopen after verify() which modifies stream pointer
            stream.seek(0)
            img = Image.open(stream)
            width, height = img.size
            format_name = img.format or "IMAGE"

            # Check for embedded text metadata (PNG text chunks or EXIF description)
            embedded_text = ""
            if hasattr(img, "info") and img.info:
                for k, v in img.info.items():
                    if isinstance(v, str) and len(v) > 10:
                        embedded_text += f"{v}\n"

            # Check if image dimensions are reasonable for an official document
            if width < 50 or height < 50:
                return ExtractedFileContent(
                    filename=filename,
                    content_type=f"image/{format_name.lower()}",
                    text="",
                    is_readable=False,
                    is_corrupted=False,
                    error_message=f"Image resolution too low ({width}x{height}) for document scrutiny.",
                    metadata={"width": width, "height": height, "format": format_name},
                )

            # Return image details with any embedded description
            meta = {"width": width, "height": height, "format": format_name, "mode": img.mode}
            return ExtractedFileContent(
                filename=filename,
                content_type=f"image/{format_name.lower()}",
                text=embedded_text.strip(),
                page_count=1,
                is_readable=True,
                metadata=meta,
            )

        except (UnidentifiedImageError, OSError, Exception) as exc:
            logger.warning("Image verification error for %s: %s", filename, exc)
            return ExtractedFileContent(
                filename=filename,
                content_type=content_type or "image/unknown",
                text="",
                is_readable=False,
                is_corrupted=True,
                error_message=f"Image file is corrupted or not a valid image format: {exc}",
            )

    # 4. Unknown / Unsupported format
    return ExtractedFileContent(
        filename=filename,
        content_type=content_type or "application/octet-stream",
        text="",
        is_readable=False,
        is_corrupted=False,
        error_message=f"Unsupported file format '{filename}'. Supported formats are PDF, PNG, JPG, JPEG, TXT.",
    )

