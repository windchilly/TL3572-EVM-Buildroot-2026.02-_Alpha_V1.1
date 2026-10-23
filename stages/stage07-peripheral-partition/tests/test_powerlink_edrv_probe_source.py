from pathlib import Path
import importlib.util
import struct
import sys
import unittest
import zlib
STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'tests/board'))
from powerlink_edrv_checks import frame, validate_result, accept_response, OWN_MAC
sys.path.pop(0)
VALID = ('PLK UP2 EDRV rc=0 clean=1 nonce=0x1 rx=64 submitted=64 tx=64 fcs=64 '
         'rxerr=0 txerr=0 fatal=0 drop=0 mac=0xc003 stop=0x0/0x0/0x0/0x0/0x0/0x0 lease=0/0')

class EdrvProbeTests(unittest.TestCase):
    def test_codec_lengths_fields_crc(self):
        for sequence in range(64):
            packet = frame(OWN_MAC, bytes.fromhex('025550330003'), 0x35720001, sequence, 1)
            self.assertEqual(len(packet), 64 if sequence < 32 else 1514)
            self.assertEqual(packet[14:22], b'M7EDRV01')
            self.assertEqual(struct.unpack_from('!4I', packet, 22), (0x35720001, 1, sequence, len(packet) - 42))
            self.assertEqual(zlib.crc32(packet[14:-4]), struct.unpack('!I', packet[-4:])[0])

    def test_codec_bounds(self):
        for seq in (-1, 64, 1000):
            with self.assertRaises(ValueError): frame(OWN_MAC, OWN_MAC, 1, seq, 1)
        with self.assertRaises(ValueError): frame(OWN_MAC, OWN_MAC, 1, 0, 3)

    def test_physical_result(self):
        self.assertEqual(validate_result(VALID)['fcs'], '64')
        for old, new in [('rx=64', 'rx=63'), ('tx=64', 'tx=65'), ('fcs=64', 'fcs=0'),
                         ('clean=1', 'clean=0'), ('rxerr=0', 'rxerr=1'), ('txerr=0', 'txerr=1'),
                         ('fatal=0', 'fatal=1'), ('lease=0/0', 'lease=0/2'), ('mac=0xc003', 'mac=0xe003')]:
            with self.subTest(new=new), self.assertRaises(ValueError): validate_result(VALID.replace(old, new))

    def test_peer_never_accepts_outgoing_or_stale(self):
        packet = frame(OWN_MAC, OWN_MAC, 1, 0, 2)
        self.assertFalse(accept_response(packet, ('eth2', 0, 4), packet, 1))
        self.assertFalse(accept_response(packet, ('eth2', 0, 0), packet, 2))
        self.assertTrue(accept_response(packet, ('eth2', 0, 0), packet, 1))
        with self.assertRaises(ValueError): accept_response(packet[:-1] + b'\xff', ('eth2', 0, 0), packet, 1)

    def test_board_fixed_limit_and_no_mn(self):
        text = (STAGE / 'tests/board/run_powerlink_edrv_probe.py').read_text()
        self.assertIn('for sequence in range(TOTAL):', text)
        self.assertIn('if text not in ALLOWED:', text)
        self.assertIn("if address[2] == 4", (STAGE / 'tests/board/powerlink_edrv_checks.py').read_text())
        for name in ('PLK env-init', 'PLK reset', 'M7 run', '--count', 'reboot('): self.assertNotIn(name, text)
        self.assertIn('NEVER resubmit frames/commands', text)

    def test_probe_real_driver_no_mn_or_timer(self):
        text = (STAGE / 'source/powerlink/port/m7_edrv_probe.c').read_text()
        for name in ('edrv_init(&init)', 'm7_edrv_poll(8)', 'edrv_sendTxBuffer(&probe.tx)',
                     'edrv_exit()', 'target_cleanup()', 'packet[length+3]', '20000U', '40000U'):
            self.assertIn(name, text)
        for name in ('oplk_initialize(', 'oplk_create(', 'hrestimer_init(', 'm7_plk_timer_acquire(', 'malloc('):
            self.assertNotIn(name, text)
        self.assertIn('if (m7_eth2_hw_lease()) goto unsafe;', text)
        self.assertEqual(text.count('edrv_exit()'), 1)

    def test_mailbox_default_off_and_static_lifetime(self):
        patch = (STAGE / 'source/patches/uniproton/0017-rk3572-powerlink-edrv-probe.patch').read_text()
        self.assertIn('diagnostic" OFF)', patch)
        self.assertIn('NOT MCS_CLIENT_CPU_ID STREQUAL "5"', patch)
        app = (STAGE / 'source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_powerlink_app.c').read_text()
        self.assertIn('command == EDRV_PROBE && snapshot.mn.state != M7_MN_COLD', app)
        self.assertIn('if (!edrv.clean)', app)
        text = (STAGE / 'source/powerlink/port/m7_edrv_probe.c').read_text()
        self.assertIn('tEdrvTxBuffer tx;', text.split('} probe;')[0])
        self.assertNotIn('m7_edrv_probe(', app.split('uint32_t Rk3572PowerlinkInit(void)')[1].split('static int matches')[0])

if __name__ == '__main__': unittest.main()
