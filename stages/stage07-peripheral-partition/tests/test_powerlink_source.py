import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "prepare_powerlink", Path(__file__).resolve().parents[1] / "build/prepare_m7_powerlink.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_powerlink", Path(__file__).resolve().parent / "audit_powerlink_core.py")
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


class PowerlinkArchiveTests(unittest.TestCase):
    def member(self, name="upstream/stack/file.c", kind=tarfile.REGTYPE):
        member = tarfile.TarInfo(name)
        member.type = kind
        return member

    def test_regular_file(self):
        MODULE.validate_members([self.member()], "upstream", 1)

    def test_directory(self):
        MODULE.validate_members([self.member("upstream/stack", tarfile.DIRTYPE)], "upstream", 0)

    def test_unsafe_paths(self):
        for name in ("/upstream/file", "upstream/../file", "other/file", "upstream\\file"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                MODULE.validate_members([self.member(name)], "upstream", 1)

    def test_special_files(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                MODULE.validate_members([self.member(kind=kind)], "upstream", 1)

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            MODULE.validate_members([self.member(), self.member()], "upstream", 2)

    def test_file_count(self):
        with self.assertRaises(ValueError):
            MODULE.validate_members([self.member()], "upstream", 2)

    def test_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FileExistsError):
            MODULE.prepare(Path(directory))


class PowerlinkAuditTests(unittest.TestCase):
    def test_expected_boundary(self):
        AUDIT.check_undefined(AUDIT.HAL | AUDIT.LIBC)

    def test_linux_or_atomic_dependency_rejected(self):
        for symbol in ("socket", "pcap_open_live", "pthread_create", "fopen", "__aarch64_swp1_acq_rel"):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                AUDIT.check_undefined(AUDIT.HAL | {symbol})

    def test_fake_hal_success_rejected(self):
        with self.assertRaises(ValueError):
            AUDIT.check_undefined((AUDIT.HAL | AUDIT.LIBC) - {"edrv_init"})

    def test_fp_simd_instructions_rejected(self):
        for assembly in ("fadd d0, d1, d2", "ldr q2, [x1]", "str d3, [x1]", "add v0.16b, v1.16b, v2.16b"):
            with self.subTest(assembly=assembly):
                self.assertTrue(AUDIT.forbidden_instructions("   0: 00000000 " + assembly))

    def test_integer_instructions_accepted(self):
        self.assertEqual(AUDIT.forbidden_instructions("   0: 00000000 add x0, x1, x2\n   4: 00000000 b d0 <func>"), [])


if __name__ == "__main__":
    unittest.main()
