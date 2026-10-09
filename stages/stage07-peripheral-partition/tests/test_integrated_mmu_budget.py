import unittest

from audit_integrated_mmu import table_budget


def region(address, size=0x1000, level=3):
    return (address, address, size, level, 0)


class BudgetTests(unittest.TestCase):
    def test_shared_l3_table_is_reused(self):
        result = table_budget([region(0x26074000), region(0x26090000)], 3 * 4096)
        self.assertEqual(result['table_pages'], 3)
        self.assertTrue(result['fits'])

    def test_different_l3_block_costs_another_page(self):
        result = table_budget([region(0x26074000), region(0x26500000)], 3 * 4096)
        self.assertEqual(result['table_pages'], 4)
        self.assertEqual(result['first_overflow_region'], '0x26500000')
        self.assertFalse(result['fits'])

    def test_l2_blocks_do_not_allocate_l3_table(self):
        result = table_budget([region(0x7b200000, 0x800000, 2)], 2 * 4096)
        self.assertEqual(result['table_pages'], 2)
        self.assertTrue(result['fits'])

    def test_unsupported_or_unaligned_maps_rejected(self):
        for regions in ([region(2**32)], [region(0x26074001)], [], [region(0x26074000, level=1)]):
            with self.assertRaises(ValueError):
                table_budget(regions, 0x8000)


if __name__ == '__main__':
    unittest.main()
