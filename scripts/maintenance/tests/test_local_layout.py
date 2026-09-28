"""Check the physical layout, retained inputs and active documentation links."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[3]
PLAN = json.loads((ROOT / "docs/operations/local-reorganization-plan.json").read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class LocalLayoutTests(unittest.TestCase):
    def test_legacy_roots_are_absent(self):
        for name in PLAN["remove_empty_roots"]:
            with self.subTest(name=name):
                self.assertFalse((ROOT / name).exists())

    def test_original_tracked_files_are_retained_or_explicitly_recycled(self):
        original = subprocess.check_output([
            "git", "-C", str(ROOT), "ls-tree", "-rz", "--name-only", PLAN["baseline_commit"]
        ]).decode("utf-8").split("\0")
        removed = {item["source"] for item in PLAN["recycle"]}
        for path in filter(None, original):
            if path in removed:
                continue
            expected = path
            for move in PLAN["moves"]:
                if path == move["source"] or path.startswith(move["source"] + "/"):
                    expected = move["destination"] + path[len(move["source"]):]
                    break
            with self.subTest(original=path, expected=expected):
                self.assertTrue((ROOT / expected).is_file())

    def test_all_stage_source_archive_hashes(self):
        count = 0
        for relative in ("repro-inputs/all-stages", "repro-inputs/all-stages/historical"):
            directory = ROOT / relative
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                checksum, name = line.split(None, 1)
                with self.subTest(name=name):
                    self.assertEqual(digest(directory / name.strip()), checksum)
                count += 1
        self.assertEqual(count, 24)

    def test_pinned_toolchain_hash(self):
        path = ROOT / "software/toolchains/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu.tar.gz"
        self.assertEqual(digest(path), "c7609e94851a47a5f475fb91eee091c8ca9eef13f31bad2e43d12d11bb1f7861")

    def test_active_local_markdown_links(self):
        documents = (
            "README.md", "hardware/README.md", "software/README.md", "docs/README.md",
            "docs/project/migration-plan.md", "docs/operations/workspace-layout.md",
            "docs/operations/local-reorganization-20260928.md",
            "stages/stage07-peripheral-partition/docs/m7.0-resource-allocation-and-tests.md",
        )
        for name in documents:
            document = ROOT / name
            contents = document.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", contents):
                link = link.strip("<>").split("#", 1)[0]
                if not link or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link):
                    continue
                with self.subTest(document=name, link=link):
                    self.assertTrue((document.parent / unquote(link)).exists())

    @unittest.skipUnless((ROOT / ".local-only/maintenance/local-reorganization-20260928.json").exists(), "Local-only execution inventory")
    def test_unedited_moved_files_keep_their_hashes(self):
        report = json.loads((ROOT / ".local-only/maintenance/local-reorganization-20260928.json").read_text(encoding="utf-8-sig"))
        updated_docs = {
            "docs/project/migration-plan.md", "docs/operations/github-upload-scope.md",
            "docs/vendor-notes/sdk/LOCAL_ARCHIVE.md",
        }
        self.assertEqual(report["moved_files"], 774)
        self.assertEqual(report["verified_files"], 774)
        for entry in report["inventory"]:
            if entry["destination"] in updated_docs:
                continue
            with self.subTest(path=entry["destination"]):
                self.assertEqual(digest(ROOT / entry["destination"]), entry["sha256"])


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
