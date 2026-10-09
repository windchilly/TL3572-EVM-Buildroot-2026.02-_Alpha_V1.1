import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parent / 'board'))
from integrated_mmu_resources import verify_tables


class TableTests(unittest.TestCase):
    def fixture(self):
        root = 0x7ba00000
        data = bytearray(3 * 4096)
        region = [(0x26074000, 0x26074000, 4096, 3, 0x60000000000400)]
        struct.pack_into('<Q', data, 0, (root + 4096) | 3)
        struct.pack_into('<Q', data, 4096 + 304 * 8, (root + 8192) | 3)
        struct.pack_into('<Q', data, 8192 + 116 * 8, 0x60000026074403)
        return region, root, data

    def test_complete_actual_pte(self):
        self.assertEqual(verify_tables(*self.fixture()), dict(table_pages=3, mapped_units=1))

    def test_missing_wrong_and_out_of_range_table_rejected(self):
        for position, value in ((0, 0), (0, 0x7ba10003), (8192 + 116 * 8, 0x26074403)):
            regions, root, data = self.fixture()
            struct.pack_into('<Q', data, position, value)
            with self.assertRaises(RuntimeError):
                verify_tables(regions, root, data)
