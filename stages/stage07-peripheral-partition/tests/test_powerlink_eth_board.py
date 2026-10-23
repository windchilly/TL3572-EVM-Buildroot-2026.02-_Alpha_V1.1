import importlib.util
import ast
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
STAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('plk_eth_checks', STAGE / 'tests/board/powerlink_eth_checks.py')
CHECK = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CHECK)
VALID = ('PLK UP2 ETH rc=0 clean=1 phy=0x7b74/0x4412 bmcr=0x2000 bmsr=0x2004 '
         'mac=0xc000 tx=0x0 rx=0x0 dma=0x0 irq=0x0/0x0 stop=0x0/0x0/0x0/0x0/0x0/0x0 lease=0/0')

class EthBoardTests(unittest.TestCase):
    def test_complete_readback(self):
        self.assertEqual(CHECK.validate_probe(VALID)['bmcr'], '0x2000')

    def test_safe_failure_is_not_pass(self):
        failed = VALID.replace('rc=0', 'rc=4')
        self.assertTrue(CHECK.quiescent(CHECK.fields(failed, 'PLK UP2 ETH')))
        with self.assertRaises(ValueError): CHECK.validate_probe(failed)

    def test_incomplete_or_unclean_stop_rejected(self):
        for old, new in [('clean=1', 'clean=0'), ('lease=0/0', 'lease=0/2'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0x1/0x0/0x0/0x0/0x0/0x0'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0x0/0x1/0x0/0x0/0x0/0x0'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0x0/0x0/0x1/0x0/0x0/0x0'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0x0/0x0/0x0/0x1/0x0/0x0'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0x0/0x0/0x0/0x0/0x1/0x0'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0x0/0x0/0x0/0x0/0x0/0x1'),
                         ('stop=0x0/0x0/0x0/0x0/0x0/0x0', 'stop=0')]:
            with self.subTest(new=new):
                self.assertFalse(CHECK.quiescent(CHECK.fields(VALID.replace(old, new), 'PLK UP2 ETH')))

    def test_bad_phy_mac_dma_not_accepted(self):
        for old, new in [('bmcr=0x2000', 'bmcr=0x2100'), ('bmcr=0x2000', 'bmcr=0x3000'),
                         ('phy=0x7b74/0x4412', 'phy=0x7b74/0x4413'), ('bmsr=0x2004', 'bmsr=0x2000'),
                         ('mac=0xc000', 'mac=0xe000'), ('mac=0xc000', 'mac=0xc003'),
                         ('tx=0x0', 'tx=0x1'), ('rx=0x0', 'rx=0x1'), ('dma=0x0', 'dma=0x1'),
                         ('irq=0x0/0x0', 'irq=0x0/0x1')]:
            with self.subTest(new=new), self.assertRaises(ValueError): CHECK.validate_probe(VALID.replace(old, new))

    def test_bad_message_rejected(self):
        for message in (VALID.replace('UP2', 'UP1'), VALID + ' rc=0', VALID + ' malformed', 'PLK UP2 ETH clean=1'):
            with self.subTest(message=message), self.assertRaises(ValueError): CHECK.validate_probe(message)

    def test_peer_mode(self):
        self.assertEqual(CHECK.link_mode('Settings for eth2:\n Speed: 100Mb/s\n Duplex: Half\n Auto-negotiation: on\n Link detected: yes\n'),
            {'Speed': '100Mb/s', 'Duplex': 'Half', 'Auto-negotiation': 'on', 'Link detected': 'yes'})

    def test_runner_allowlist_and_retention(self):
        text = (STAGE / 'tests/board/run_powerlink_eth_probe.py').read_text()
        self.assertIn("if text not in ALLOWED", text)
        for name in ('socket', 'M7 run', 'PLK timer-probe', 'PLK env-init', 'ethtool\', \'-s', 'reboot('):
            self.assertNotIn(name, text)
        self.assertIn('UNSAFE/UNKNOWN: retain temporary UP2 and shared power/root hold', text)
        self.assertLess(text.index('if not safe:'), text.index("common.control('stop', CLIENT)"))
        self.assertIn('safe = False; start_attempted = True;', text)

    def test_management_lifetime_is_not_drift(self):
        tree = ast.parse((STAGE / 'tests/board/run_powerlink_eth_probe.py').read_text())
        function = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'management')
        info = {'family': 'inet', 'local': '192.168.2.141', 'prefixlen': 24, 'scope': 'global', 'valid_life_time': 100}
        def path(value):
            name = '29d20000.ethernet' if value.endswith('/device') else 'rk_gmac-dwmac'
            return SimpleNamespace(resolve=lambda: SimpleNamespace(name=name), read_text=lambda: '0-3,6-7\n')
        def command(*args):
            return json.dumps([{'addr_info': [info]}]) if '-j' in args else 'fixed-route'
        namespace = {'Path': path, 'common': SimpleNamespace(command=command), 'json': json}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<management-test>', 'exec'), namespace)
        first = namespace['management'](); info['valid_life_time'] = 98
        self.assertEqual(first, namespace['management']())
        info['local'] = '192.168.2.142'
        with self.assertRaises(RuntimeError): namespace['management']()

    def test_snapshot_and_exception_layout(self):
        sys.path.insert(0, str(STAGE / 'tests/board'))
        try:
            spec = importlib.util.spec_from_file_location('plk_eth_dram', STAGE / 'tests/board/read_powerlink_eth_snapshot.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            raw = bytearray(520); struct.pack_into('<I', raw, 120, 6)
            struct.pack_into('<Q', raw, 232, 0x7c20fe68); struct.pack_into('<Q', raw, 256, 0x02000000)
            self.assertEqual(module.decode_exception(raw)['elr'], '0x7c20fe68')
            self.assertEqual(module.decode_exception(raw)['ec'], 0)
            self.assertEqual(module.decode(bytes(400))['eth']['clean'], 0)
            with self.assertRaises(ValueError): module.decode(bytes(304))
            with self.assertRaises(ValueError): module.decode_exception(bytes(521))
        finally: sys.path.pop(0)

if __name__ == '__main__': unittest.main()
