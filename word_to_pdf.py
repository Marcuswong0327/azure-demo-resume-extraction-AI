"""Convert legacy Word resumes to PDF for in-browser viewing of archive URLs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional, Protocol, Tuple


class SupportsConvertToPdf(Protocol):
    def convert(self, data: bytes, source_filename: str) -> bytes: ...


def prepare_archive_payload(
    data: bytes,
    filename: str,
    converter: Optional[SupportsConvertToPdf] = None,
) -> Tuple[bytes, str]:
    """
    Return bytes + filename to store in blob.

    Word files are converted to PDF so Azure URLs open in the browser.
    PDF/TXT (and anything else) pass through unchanged.
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ("doc", "docx"):
        return data, filename

    active = converter if converter is not None else WordToPdfConverter()
    pdf_bytes = active.convert(data, filename)
    pdf_name = f"{Path(filename).stem}.pdf"
    return pdf_bytes, pdf_name


class WordToPdfConverter:
    """LibreOffice (soffice) headless Word → PDF. Single responsibility: conversion."""

    def __init__(
        self,
        soffice: Optional[str] = None,
        run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self._soffice = soffice
        self._run = run

    def _resolve_soffice(self) -> str:
        if self._soffice:
            return self._soffice
        for name in ("soffice", "libreoffice"):
            found = shutil.which(name)
            if found:
                return found
        raise RuntimeError(
            "LibreOffice (soffice) is required to convert Word to PDF for browser "
            "viewing. Install libreoffice-writer on the host (Railway Dockerfile) "
            "or keep the original .doc/.docx URL."
        )

    def convert(self, data: bytes, source_filename: str) -> bytes:
        soffice = self._resolve_soffice()
        suffix = Path(source_filename).suffix.lower() or ".docx"
        if suffix not in (".doc", ".docx"):
            suffix = ".docx"

        with tempfile.TemporaryDirectory(prefix="word2pdf-") as tmp:
            src_path = os.path.join(tmp, f"input{suffix}")
            with open(src_path, "wb") as fh:
                fh.write(data)

            result = self._run(
                [
                    soffice,
                    "--headless",
                    "--nologo",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmp,
                    src_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(
                    f"LibreOffice failed converting {source_filename!r} "
                    f"(exit {result.returncode}): {err or 'no output'}"
                )

            pdf_path = os.path.join(tmp, "input.pdf")
            if not os.path.exists(pdf_path):
                raise RuntimeError(
                    f"LibreOffice did not produce a PDF for {source_filename!r}."
                )
            with open(pdf_path, "rb") as fh:
                return fh.read()
