"""TDD: Word (.doc/.docx) → PDF for browser-viewable Azure archive URLs."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from word_to_pdf import WordToPdfConverter, prepare_archive_payload


class TestPrepareArchivePayload(unittest.TestCase):
    def test_pdf_and_txt_pass_through_unchanged(self):
        data = b"%PDF-1.4"
        out_data, out_name = prepare_archive_payload(data, "resume.pdf")
        self.assertEqual(out_data, data)
        self.assertEqual(out_name, "resume.pdf")

        text = b"hello"
        out_data, out_name = prepare_archive_payload(text, "notes.txt")
        self.assertEqual(out_data, text)
        self.assertEqual(out_name, "notes.txt")

    def test_docx_uses_converter_and_renames_to_pdf(self):
        fake = MagicMock()
        fake.convert.return_value = b"%PDF-fake"
        out_data, out_name = prepare_archive_payload(
            b"PK...", "Candidate.docx", converter=fake
        )
        fake.convert.assert_called_once_with(b"PK...", "Candidate.docx")
        self.assertEqual(out_data, b"%PDF-fake")
        self.assertEqual(out_name, "Candidate.pdf")

    def test_doc_uses_converter_and_renames_to_pdf(self):
        fake = MagicMock()
        fake.convert.return_value = b"%PDF-legacy"
        out_data, out_name = prepare_archive_payload(
            b"\xd0\xcf", "old.doc", converter=fake
        )
        self.assertEqual(out_data, b"%PDF-legacy")
        self.assertEqual(out_name, "old.pdf")


class TestWordToPdfConverter(unittest.TestCase):
    def test_raises_when_soffice_missing(self):
        with patch("word_to_pdf.shutil.which", return_value=None):
            converter = WordToPdfConverter()
            with self.assertRaises(RuntimeError) as ctx:
                converter.convert(b"data", "x.docx")
            self.assertIn("LibreOffice", str(ctx.exception))

    def test_convert_invokes_soffice_and_returns_pdf_bytes(self):
        run = MagicMock()

        def fake_run(cmd, **kwargs):
            # LibreOffice would write input.pdf next to the source in --outdir.
            outdir = cmd[cmd.index("--outdir") + 1]
            pdf_path = os.path.join(outdir, "input.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"%PDF-converted")
            return MagicMock(returncode=0, stderr="", stdout="")

        run.side_effect = fake_run

        def fake_which(name):
            return "/usr/bin/soffice" if name in ("soffice", "libreoffice") else None

        with patch("word_to_pdf.shutil.which", side_effect=fake_which):
            converter = WordToPdfConverter(run=run)
            result = converter.convert(b"word-bytes", "resume.docx")

        self.assertEqual(result, b"%PDF-converted")
        self.assertTrue(run.called)
        args = run.call_args[0][0]
        self.assertIn("--headless", args)
        self.assertIn("--convert-to", args)
        self.assertIn("pdf", args)


if __name__ == "__main__":
    unittest.main()
