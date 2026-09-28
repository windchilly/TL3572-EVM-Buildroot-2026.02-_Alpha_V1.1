#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from archive_utils import archive


class SourceArchiveTests(unittest.TestCase):
    def test_sorted_deterministic_archive(self):
        with tempfile.TemporaryDirectory(prefix="tl3572-source-test-") as directory:
            root = Path(directory)
            source = root / "source.c"
            source.write_text("int example;\n")
            first = archive(root / "first.tar.gz", [(source, "source.c")])
            os.utime(source, (12, 12))
            second = archive(root / "second.tar.gz", [(source, "source.c")])
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["files"], second["files"])

    @unittest.skipUnless(sys.platform == "linux", "Linux source symlinks")
    def test_internal_parent_symlink_is_retained(self):
        with tempfile.TemporaryDirectory(prefix="tl3572-source-test-") as directory:
            root = Path(directory)
            (root / "dir").mkdir()
            (root / "source.c").write_text("int example;\n")
            link = root / "dir/source.c"
            link.symlink_to("../source.c")
            archive(root / "source.tar.gz", [(link, "dir/source.c"), (root / "source.c", "source.c")])
            with tarfile.open(root / "source.tar.gz") as source:
                self.assertEqual(source.getmember("dir/source.c").linkname, "../source.c")

    @unittest.skipUnless(sys.platform == "linux", "Linux source symlinks")
    def test_escaping_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tl3572-source-test-") as directory:
            root = Path(directory)
            link = root / "source.c"
            link.symlink_to("../../outside.c")
            with self.assertRaises(ValueError):
                archive(root / "source.tar.gz", [(link, "source.c")])

    def test_lfs_pointer_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tl3572-source-test-") as directory:
            root = Path(directory)
            source = root / "source.c"
            source.write_text("version https://git-lfs.github.com/spec/v1\n")
            with self.assertRaises(ValueError):
                archive(root / "source.tar.gz", [(source, "source.c")])


if __name__ == "__main__":
    unittest.main()
