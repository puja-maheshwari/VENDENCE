import tempfile
import unittest
from pathlib import Path
import ui


class PreviewPathTests(unittest.TestCase):
    def test_saved_path_inside_store_only_and_no_filename_guessing(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); store = root / "uploads/1"; store.mkdir(parents=True)
            saved = store / "original.pdf"; saved.write_bytes(b"synthetic")
            outside = root / "private.txt"; outside.write_text("synthetic unrelated content")
            self.assertEqual(ui._resolve_preview({"file_path": str(saved)}, root), saved.resolve())
            self.assertIsNone(ui._resolve_preview({"file_path": str(outside)}, root))
            self.assertIsNone(ui._resolve_preview({"file_name": "original.pdf"}, root))
            link = store / "outside.pdf"; link.symlink_to(outside)
            self.assertIsNone(ui._resolve_preview({"file_path": str(link)}, root))
