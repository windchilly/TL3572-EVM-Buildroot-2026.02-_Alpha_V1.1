import importlib.util
import pathlib
import struct
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "source" / "host" / "up_log_reader.py"
SPEC = importlib.util.spec_from_file_location("up_log_reader", MODULE_PATH)
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def make_region(cpu=4, seq=0, boot=1):
    region = bytearray(reader.REGION_SIZE)
    struct.pack_into(
        "<8I", region, 0, reader.MAGIC, reader.VERSION, cpu,
        reader.RECORD_SIZE, reader.RECORD_COUNT, boot, seq, 0,
    )
    return region


def add_record(region, seq, boot, message, committed=True):
    offset = reader.HEADER_SIZE + ((seq - 1) % reader.RECORD_COUNT) * reader.RECORD_SIZE
    payload = message.encode()
    struct.pack_into("<4I", region, offset, seq if committed else 0, boot, len(payload), 0)
    region[offset + 16 : offset + 16 + len(payload)] = payload


class UpLogReaderTest(unittest.TestCase):
    def test_header_is_bound_to_instance(self):
        region = make_region(cpu=4, seq=2)
        self.assertEqual(reader.read_header(region, 4), (1, 2, 0))
        self.assertIsNone(reader.read_header(region, 5))

    def test_reads_committed_records_only(self):
        region = make_region(seq=3)
        add_record(region, 1, 1, "boot\n")
        add_record(region, 2, 1, "ready\n")
        add_record(region, 3, 1, "partial", committed=False)
        first, records = reader.read_new_records(region, 0, 3)
        self.assertEqual(first, 1)
        self.assertEqual(records, [(1, 1, "boot\n"), (2, 1, "ready\n")])

    def test_reports_ring_overwrite_boundary(self):
        seq = reader.RECORD_COUNT + 2
        region = make_region(seq=seq)
        add_record(region, seq, 1, "latest")
        first, records = reader.read_new_records(region, 0, seq)
        self.assertEqual(first, 3)
        self.assertEqual(records, [(seq, 1, "latest")])

    def test_monitor_marks_client_and_boot(self):
        region = make_region(cpu=5, seq=1, boot=2)
        add_record(region, 1, 2, "ready\n")
        messages = []
        reader.monitor(region, "up-b", 5, False, 0.2, messages.append)
        self.assertEqual(messages, [
            "[up-b] boot=2 seq=1",
            "[up-b boot=2 seq=1] ready\n",
        ])

    def test_file_emitter_separates_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = pathlib.Path(directory)
            up_a = reader.FileEmitter(output_dir, "up-a")
            up_b = reader.FileEmitter(output_dir, "up-b")
            up_a("first\n")
            up_b("second\n")
            up_a.close()
            up_b.close()
            self.assertIn("first", (output_dir / "up-a.log").read_text(encoding="utf-8"))
            self.assertNotIn("second", (output_dir / "up-a.log").read_text(encoding="utf-8"))
            self.assertIn("second", (output_dir / "up-b.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
