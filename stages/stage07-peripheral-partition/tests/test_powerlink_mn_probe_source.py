from pathlib import Path
import sys
import unittest
STAGE = Path(__file__).resolve().parents[1]
PORT = STAGE / 'source/powerlink/port'
APP = STAGE / 'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'
sys.path.insert(0, str(STAGE / 'tests/board'))
from powerlink_mn_checks import validate_lifecycle
sys.path.pop(0)

class MnLifecycleSourceTests(unittest.TestCase):
    def test_real_stack_lifecycle_without_nmt_commands(self):
        text = (PORT / 'm7_mn_probe.c').read_text()
        for name in ('m7_mn_initialize()', 'm7_mn_prepare()', 'm7_mn_process()', 'm7_mn_stop()',
                     'm7_mn_exit()', 'nmtu_getNmtState() == kNmtGsOff'):
            self.assertIn(name, text)
        for name in ('oplk_execNmtCommand(', 'edrv_sendTxBuffer(', 'oplk_sendAsyncFrame(',
                     'malloc(', 'm7_mn_stop(); /* retry', 'hrestimer_exit('): self.assertNotIn(name, text)
        self.assertEqual(text.count('m7_mn_stop()'), 1)

    def test_bounded_and_terminal(self):
        text = (PORT / 'm7_mn_probe.c').read_text()
        self.assertIn('while (out->loops < M7_MN_PROBE_LOOPS)', text)
        self.assertIn('>= 2000U', text)
        self.assertIn('m7_plk_sleep(1U)', text)
        self.assertIn('m7_plk_fault(); return out->result = result;', text)
        self.assertIn('out->clean = 1; entered = 0;', text)
        self.assertIn('#define M7_MN_PROBE_LOOPS 128U', (PORT / 'm7_mn_probe.h').read_text())

    def test_no_tx_proof_is_not_only_completion_counter(self):
        text = (PORT / 'm7_mn_probe.c').read_text()
        self.assertIn('dma->tx[i].d[word]', text)
        self.assertIn('!out->txDescriptors', text)
        self.assertIn('!timer.interrupts && !timer.callbacks', text)
        self.assertIn('quietTimer(&out->timerInitial, &out->timerFinal)', text)

    def test_default_off_up2_only(self):
        text = (STAGE / 'source/patches/uniproton/0018-rk3572-powerlink-mn-probe.patch').read_text()
        self.assertIn('diagnostic" OFF)', text)
        self.assertIn('NOT MCS_CLIENT_CPU_ID STREQUAL "5"', text)
        self.assertIn('NOT M7_POWERLINK_EDRV_PROBE', text)

    def test_mailbox_and_cached_diagnostics(self):
        text = (APP / 'rk3572_powerlink_app.c').read_text()
        self.assertIn('command == MN_PROBE && snapshot.mn.state != M7_MN_COLD', text)
        self.assertIn('if (!lifecycle.clean)', text)
        self.assertIn('snapshot.mn = lifecycle.final', text)
        self.assertIn('"GsOff-diagnostic"', text)
        init = text.split('uint32_t Rk3572PowerlinkInit(void)')[1].split('static int matches')[0]
        self.assertNotIn('m7_mn_probe(', init)
        self.assertNotIn('m7_mn_prepare(', init)

    def test_board_result_rejects_incomplete_or_active(self):
        reply = ('PLK UP2 MN rc=0 clean=1 stage=5 stack=0x0 loops=128 state=0 nmt=0x0 rx=0 tx=0 txdesc=0 '
                 'drop=0 rxerr=0 txerr=0 fatal=0 irqs=0 callbacks=0 mac=0xc003 '
                 'stop=0x0/0x0/0x0/0x0/0x0/0x0 lease=0/0 timer=0/0')
        self.assertEqual(validate_lifecycle(reply)['loops'], '128')
        for old, new in [('loops=128', 'loops=127'), ('timer=0/0', 'timer=0/1'), ('state=0', 'state=2'),
                         ('txdesc=0', 'txdesc=1'), ('clean=1', 'clean=0'), ('irqs=0', 'irqs=1'), ('nmt=0x0', 'nmt=0x1')]:
            with self.subTest(new=new), self.assertRaises(ValueError): validate_lifecycle(reply.replace(old, new))

    def test_board_no_network_or_reset_commands(self):
        text = (STAGE / 'tests/board/run_powerlink_mn_probe.py').read_text()
        self.assertIn('--confirm-isolated-gsoff-lifecycle', text)
        self.assertIn('if text not in ALLOWED:', text)
        self.assertIn('Observe ONLY; never resubmit', text)
        for name in ('import socket', 'sendto(', 'PLK reset', 'PLK edrv-probe', 'M7 run', 'reboot('):
            self.assertNotIn(name, text)

if __name__ == '__main__': unittest.main()
