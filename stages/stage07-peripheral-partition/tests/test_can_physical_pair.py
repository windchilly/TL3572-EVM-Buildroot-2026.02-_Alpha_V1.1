#!/usr/bin/env python3
"""Unit tests for the board physical CAN pair test frame codec."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parent / "board/can_physical_pair_test.py"
SPEC = importlib.util.spec_from_file_location("can_physical_pair_test", SCRIPT)
CAN_TEST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAN_TEST)


class CanPhysicalPairCodecTests(unittest.TestCase):
    def test_classic_frame_round_trip(self):
        frame, payload = CAN_TEST.encode(0x321, b"A", 42, False)
        self.assertEqual(len(frame), 16)
        can_id, decoded, flags = CAN_TEST.decode(frame, False)
        self.assertEqual((can_id, decoded, flags), (0x321, payload, 0))
        self.assertEqual(len(decoded), 8)

    def test_fd_frame_round_trip_with_brs(self):
        frame, payload = CAN_TEST.encode(0x456, b"B", 65537, True)
        self.assertEqual(len(frame), 72)
        can_id, decoded, flags = CAN_TEST.decode(frame, True)
        self.assertEqual(can_id, 0x456)
        self.assertEqual(decoded, payload)
        self.assertEqual(len(decoded), 64)
        self.assertTrue(flags & CAN_TEST.CANFD_BRS)

    def test_sequence_is_encoded_big_endian(self):
        _, payload = CAN_TEST.encode(0x123, b"A", 0x01020304, False)
        self.assertEqual(payload[:5], b"A\x01\x02\x03\x04")


if __name__ == "__main__":
    unittest.main()
