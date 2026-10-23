"""Pure P3g board gates and mocked cleanup order; never accesses a board."""
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'tests/board'))
import powerlink_nmt_checks as checks
import run_powerlink_nmt_probe as runner
import read_powerlink_nmt_snapshot as reader
sys.path.pop(0)
REPLY = ('PLK UP2 NMT rc=0 clean=1 stage=6 stack=0x0 reset=1 off=1 resetLoops=5 offLoops=1 reached=0x21c '
    'state=0 nmt=0x0 rx=0 tx=0 txdesc=0 rxerr=0 txerr=0 fatal=0 lease=0/0 timer=0/0')
OWNER = dict(ready='1', pending='0', running='0', seq='1', done='1', cmd='7', rc='0x0', runtime='0x0',
    state='0', nmt='0x0', mode='bounded-NMT-diagnostic', owner='6', processes='6', events='6')
CLIENTS = 'Name Assigned CPU State Service\nup-b 5 Offline\nup-a 4 Offline\n'

def fixture():
    # Offsets independent of decoder code; native/AArch64 C audit checks them.
    raw = bytearray(1504)
    struct.pack_into('<9I', raw, 0, 1, 0, 0, 1, 1, 7, 0, 0, 6)
    def mn(offset, state, processes, events):
        struct.pack_into('<5I4x2Q', raw, offset, state, 6, 0, 0, 0, processes, events)
    mn(40, 0, 6, 6)
    struct.pack_into('<16I2Q', raw, 80, 0, 1, 6, 0, 6, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
    mn(160, 1, 0, 0); mn(200, 2, 0, 0); mn(240, 0, 6, 6)
    struct.pack_into('<6I', raw, 296, 0xc003, 1, 1, 0, 0, 0)
    for offset, counter in ((360, 100), (456, 200)):
        struct.pack_into('<5Q13I', raw, offset, counter, counter, 5, 0, 0, 1, 24000000,
            2, 1, 1 << 27, 0, 0, 0, 0, 160, 0, 0x43f, 1)
    struct.pack_into('<5I', raw, 552, 1, 1, 5, 1, 0x21c)
    return raw

def evidence(): return dict(owner=OWNER.copy(), result=checks.validate_reply(REPLY))

class NmtBoardTests(unittest.TestCase):
    def test_linux_full_requires_link_and_an_on(self):
        text = 'Speed: 100Mb/s\nDuplex: Full\nAuto-negotiation: on\nLink detected: yes\n'
        ports = (SimpleNamespace(name='eth1'), SimpleNamespace(name='eth2'))
        base = SimpleNamespace(ethernet=SimpleNamespace(preflight=lambda: ports), common=SimpleNamespace(command=Mock(return_value=text)))
        self.assertEqual(runner.linux_full(base), ports)
        for old, new in (('Duplex: Full', 'Duplex: Half'), ('Auto-negotiation: on', 'Auto-negotiation: off'), ('Link detected: yes', 'Link detected: no')):
            base.common.command.return_value = text.replace(old, new)
            with self.assertRaises(RuntimeError): runner.linux_full(base)

    def test_reply_complete(self):
        result = checks.validate_reply(REPLY)
        checks.validate_owner(OWNER, result)

    def test_reply_negative(self):
        for old, new in [('rc=0', 'rc=1'), ('clean=1', 'clean=0'), ('stage=6', 'stage=5'), ('reset=1', 'reset=0'),
                         ('off=1', 'off=0'), ('resetLoops=5', 'resetLoops=0'), ('offLoops=1', 'offLoops=33'),
                         ('reached=0x21c', 'reached=0x21d'), ('txdesc=0', 'txdesc=1'), ('lease=0/0', 'lease=0/1')]:
            with self.subTest(new=new), self.assertRaises(ValueError): checks.validate_reply(REPLY.replace(old, new))
        for text in (REPLY + ' rc=0', REPLY + ' extra=0', REPLY.replace(' off=1', ''), REPLY.replace('NMT', 'MN')):
            with self.assertRaises(ValueError): checks.validate_reply(text)

    def test_owner_negative(self):
        for key, value in dict(ready='0', cmd='6', done='0', processes='128', events='0', mode='GsOff-diagnostic', owner='0').items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                checks.validate_owner(OWNER | {key: value}, checks.validate_reply(REPLY))

    def test_only_two_original_clients(self):
        checks.original_clients(CLIENTS)
        for text in (CLIENTS + 'extra 5 Running\n', CLIENTS.replace('Offline', 'Running', 1),
                     CLIENTS.replace('up-b 5', 'up-b 4'), CLIENTS.replace('up-a', 'up-a-test')):
            with self.assertRaises(ValueError): checks.original_clients(text)

    def test_snapshot_complete(self):
        report = checks.validate_snapshot(fixture())
        checks.match_replies(report, OWNER, checks.validate_reply(REPLY))
        self.assertEqual(report['lifecycle']['dropped'], 1)  # Ambient filtered traffic is not a test frame.

    def test_snapshot_old_or_truncated_abi(self):
        for size in (0, 1008, 1503, 1505):
            with self.assertRaises(ValueError): checks.validate_snapshot(bytes(size))

    def test_snapshot_mailbox_and_other_probe_rejected(self):
        for offset in (0, 4, 8, 12, 16, 20, 24, 28, 32, 576, 1048, 1368):
            raw = fixture(); raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): checks.validate_snapshot(raw)

    def test_snapshot_lifecycle_errors_leases_or_traffic(self):
        for offset in (80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124, 132, 136, 140, 144, 152, 552, 556, 560, 564, 568):
            raw = fixture(); raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): checks.validate_snapshot(raw)

    def test_snapshot_mn_state_owner_or_counters(self):
        for offset in (40, 44, 48, 56, 64, 72, 160, 164, 168, 176, 184, 192, 200, 204, 208, 216, 224, 232, 240, 244, 248, 256, 264, 272):
            raw = fixture(); raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): checks.validate_snapshot(raw)

    def test_snapshot_hardware_stop(self):
        for offset in (336, 340, 344, 348, 352, 356):
            raw = fixture(); struct.pack_into('<I', raw, offset, 1)
            with self.subTest(offset=offset), self.assertRaises(ValueError): checks.validate_snapshot(raw)

    def test_snapshot_timer_not_quiet(self):
        for offset, value in ((504, 1), (512, (1 << 27) | (1 << 30)), (516, 1 << 30), (520, 1 << 30)):
            raw = fixture(); struct.pack_into('<I', raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError): checks.validate_snapshot(raw)

    def test_snapshot_tick_or_gic_preservation(self):
        for offset in (472, 500, 508, 524, 528, 532, 536, 540, 544):
            raw = fixture()
            if offset in (524, 528): struct.pack_into('<I', raw, offset, 1 << (30 if offset == 524 else 29))
            else: raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): checks.validate_snapshot(raw)

    def test_snapshot_reply_mismatch(self):
        report = checks.validate_snapshot(fixture())
        for state, result in ((OWNER | {'events': '7'}, checks.validate_reply(REPLY)),
                              (OWNER | {'owner': '7'}, checks.validate_reply(REPLY)),
                              (OWNER | {'processes': '7'}, checks.validate_reply(REPLY.replace('resetLoops=5', 'resetLoops=6')))):
            with self.assertRaises(ValueError): checks.match_replies(report, state, result)

    def test_command_whitelist_before_io(self):
        with patch.object(runner.os, 'write') as write:
            for text in ('PLK mn-probe', 'PLK start', 'PLK env-init', 'M7 run can-classic', 'PLK nmt-probe\n'):
                with self.assertRaises(ValueError): runner.diagnostic(123, text)
            write.assert_not_called()

    def test_rpmsg_short_or_ambiguous_write(self):
        with patch.object(runner.os, 'write', return_value=1), self.assertRaises(RuntimeError): runner.diagnostic(1, 'PLK nmt-probe')
        with patch.object(runner.os, 'write', side_effect=lambda fd, data: len(data)), \
             patch.object(runner.select, 'select', return_value=([1], [], [])), \
             patch.object(runner.os, 'read', return_value=b'OK\nSTALE\n'), self.assertRaises(RuntimeError): runner.diagnostic(1, 'PLK status')

    def test_no_stop_without_valid_completion(self):
        common = SimpleNamespace(control=Mock(), confirm_up_cpus_off=Mock())
        for item in (None, evidence() | {'owner': OWNER | {'done': '0'}}):
            with self.assertRaises((RuntimeError, ValueError)): runner.stop_completed(common, Path('unused'), item)
        common.control.assert_not_called(); common.confirm_up_cpus_off.assert_not_called()

    def test_stop_exactly_once_then_private_proof(self):
        order = []; report = checks.validate_snapshot(fixture())
        common = SimpleNamespace(control=lambda *args: order.append(args), confirm_up_cpus_off=lambda: order.append('physical OFF'))
        with patch.object(runner, 'read_stopped', side_effect=lambda image: order.append('private DRAM') or report):
            self.assertEqual(runner.stop_completed(common, Path('unused'), evidence()), report)
        self.assertEqual(order, [('stop', runner.CLIENT), 'physical OFF', 'private DRAM'])

    def test_stop_failure_never_retries(self):
        common = SimpleNamespace(control=Mock(side_effect=RuntimeError('stop failed')), confirm_up_cpus_off=Mock())
        with patch.object(runner, 'read_stopped') as read, self.assertRaises(RuntimeError): runner.stop_completed(common, Path('unused'), evidence())
        common.control.assert_called_once_with('stop', runner.CLIENT); common.confirm_up_cpus_off.assert_not_called(); read.assert_not_called()

    def test_private_failure_never_second_stop(self):
        common = SimpleNamespace(control=Mock(), confirm_up_cpus_off=Mock())
        with patch.object(runner, 'read_stopped', side_effect=ValueError('bad private proof')), self.assertRaises(ValueError):
            runner.stop_completed(common, Path('unused'), evidence())
        common.control.assert_called_once_with('stop', runner.CLIENT)

    def test_one_shot_persistent_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); runner.claim_attempt(root, 'boot-test')
            with self.assertRaises(FileExistsError): runner.claim_attempt(root, 'boot-test')
            self.assertIn(checks.SHA, (root / 'ATTEMPTED').read_text())

    def test_explicit_approval_before_board_imports_or_io(self):
        with patch.object(sys, 'argv', ['run', '--sha256', checks.SHA]), \
             patch.object(runner.os, 'open') as opened, self.assertRaises(RuntimeError): runner.main()
        opened.assert_not_called()

    def test_wrong_image_never_reads_reserved_dram(self):
        common = SimpleNamespace(confirm_up_cpus_off=Mock())
        memory = SimpleNamespace(read_reserved_dram=Mock())
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'wrong.elf'; image.touch()
            with patch.dict(sys.modules, {'run_can_direct_pair': common, 'integrated_mmu_resources': memory}), self.assertRaises(RuntimeError): reader.read_stopped(image)
        memory.read_reserved_dram.assert_not_called()

    def test_restore_order_and_no_generic_commands(self):
        source = (STAGE / 'tests/board/run_powerlink_nmt_probe.py').read_text()
        self.assertEqual(source.count("diagnostic(fd, 'PLK nmt-probe')"), 1)
        self.assertLess(source.index('stopped = stop_completed'), source.index("common.control('rm', CLIENT)"))
        self.assertLess(source.index("common.control('rm', CLIENT)"), source.index("base.DRIVER / 'bind'"))
        for forbidden in ('sendto(', 'import socket', "control('stop', 'up-a')", "command('reboot'", 'M7 run'):
            self.assertNotIn(forbidden, source)
        self.assertIn('Observe ONLY', source); self.assertIn("(ROOT / 'board-result.json').open('x'", source)

if __name__ == '__main__': unittest.main()
