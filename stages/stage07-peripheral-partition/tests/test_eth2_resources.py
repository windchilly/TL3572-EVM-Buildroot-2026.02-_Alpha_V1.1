import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('eth2_resources', Path(__file__).parent / 'board/eth2_resources.py')
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class FabricGateTests(unittest.TestCase):
    def test_both_shared_roots_required(self):
        for value in (2, 4, 6, 0xffff):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                resources.validate_fabric_gate(value)

    def test_other_leaf_gates_do_not_change_root_verdict(self):
        for value in (0, 1, 0xc000, 0xfff9):
            resources.validate_fabric_gate(value)


if __name__ == '__main__':
    unittest.main()
