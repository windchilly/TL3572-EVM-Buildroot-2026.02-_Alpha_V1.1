"""Safety and idempotency tests; fake sysfs only, no board operations."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import struct
import zlib

MODULE = Path(__file__).resolve().parents[1] / "source/host/eth3_power_enable.py"
spec = importlib.util.spec_from_file_location("eth3_power_enable", MODULE)
power = importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)
smoke_spec = importlib.util.spec_from_file_location("eth3_l2_smoke", Path(__file__).parent / "board/eth3_l2_smoke.py")
smoke = importlib.util.module_from_spec(smoke_spec)
smoke_spec.loader.exec_module(smoke)


class Eth3PowerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chip = self.root / "gpiochip515"
        self.chip.mkdir()
        # A directory models the resolved device without requiring Windows symlink privileges.
        self.device = self.chip / "device"
        self.device.mkdir()
        for name, value in dict(label="1-0020", base="515", ngpio="16").items():
            (self.chip / name).write_text(value)

    def line(self, direction="out", value="0", active_low="0"):
        line = self.root / "gpio517"
        line.mkdir()
        for name, content in dict(direction=direction, value=value, active_low=active_low).items():
            (line / name).write_text(content)
        return line

    def test_dynamic_base_not_hardcoded(self):
        self.assertEqual(power.discover_gpio(self.root, self.device), 517)
        (self.chip / "base").write_text("600")
        self.assertEqual(power.discover_gpio(self.root, self.device), 602)

    def test_wrong_i2c_controller_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "reviewed"):
            power.discover_gpio(self.root, self.root / "different-controller")

    def test_wrong_width_rejected(self):
        (self.chip / "ngpio").write_text("8")
        with self.assertRaisesRegex(RuntimeError, "16 GPIOs"):
            power.discover_gpio(self.root, self.device)

    def test_absent_controller_rejected(self):
        (self.chip / "label").write_text("1-0021")
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            power.discover_gpio(self.root, self.device)

    def test_enabled_line_no_writes(self):
        self.line()
        with patch.object(Path, "write_text", side_effect=AssertionError("unnecessary write")):
            self.assertFalse(power.enable_gpio(517, self.root))

    def test_active_low_rejected_without_writes(self):
        self.line(active_low="1")
        with patch.object(Path, "write_text", side_effect=AssertionError("unsafe write")):
            with self.assertRaisesRegex(RuntimeError, "active_low"):
                power.enable_gpio(517, self.root)

    def test_only_own_direction_atomic_low(self):
        line = self.line(direction="in", value="1")
        writes = []
        real_write = Path.write_text

        def sysfs_write(path, value):
            writes.append((path, value))
            self.assertEqual((path, value), (line / "direction", "low"))
            real_write(line / "direction", "out")
            real_write(line / "value", "0")

        with patch.object(Path, "write_text", sysfs_write):
            self.assertFalse(power.enable_gpio(517, self.root))
        self.assertEqual(len(writes), 1)

    def test_failed_export_never_bypassed(self):
        with patch.object(Path, "write_text", side_effect=OSError("GPIO busy")):
            with self.assertRaisesRegex(OSError, "busy"):
                power.enable_gpio(517, self.root)

    def test_smoke_frames_mac_length_and_crc(self):
        destination, source = bytes.fromhex("00e09a42baeb"), bytes.fromhex("da14368b78f0")
        for length in (64, 1514):
            packet = smoke.frame(destination, source, 1, 999, length)
            self.assertEqual(len(packet), length)
            self.assertEqual(packet[:14], destination + source + b"\x88\xb5")
            self.assertEqual(packet[14:22], smoke.MAGIC)
            self.assertEqual(zlib.crc32(packet[14:-4]), struct.unpack("!I", packet[-4:])[0])

    def test_smoke_never_accepts_outgoing_copy(self):
        expected = smoke.frame(b"\x01" * 6, b"\x02" * 6, 1, 1, 64)
        endpoint = unittest.mock.Mock()
        endpoint.recvfrom.side_effect = [(expected, ("eth1", 0, 4)), (expected, ("eth2", 0, 0))]
        smoke.receive(endpoint, expected)
        self.assertEqual(endpoint.recvfrom.call_count, 2)

    def test_smoke_rejects_corrupt_receive(self):
        expected = smoke.frame(b"\x01" * 6, b"\x02" * 6, 1, 1, 64)
        endpoint = unittest.mock.Mock()
        endpoint.recvfrom.return_value = (expected[:-1] + bytes([expected[-1] ^ 1]), ("eth2", 0, 0))
        with self.assertRaisesRegex(RuntimeError, "CRC"):
            smoke.receive(endpoint, expected)


if __name__ == "__main__":
    unittest.main()
