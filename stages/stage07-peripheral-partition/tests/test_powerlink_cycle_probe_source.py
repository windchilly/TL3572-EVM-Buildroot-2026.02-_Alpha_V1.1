"""Guard/owner source boundaries; native production test is separate."""
from pathlib import Path
import unittest
STAGE=Path(__file__).resolve().parents[1]
PORT=STAGE/'source/powerlink/port'
APP=STAGE/'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'
class GuardSourceTests(unittest.TestCase):
    def test_default_off_and_up2_heap_gate(self):
        text=(STAGE/'source/patches/uniproton/0021-rk3572-powerlink-cycle-probe.patch').read_text(encoding='utf-8')
        self.assertIn('cycle diagnostic" OFF)',text)
        self.assertIn('NOT M7_POWERLINK_NMT_HEAP',text)
        self.assertIn('NOT MCS_CLIENT_CPU_ID STREQUAL "5"',text)
    def test_separate_pending_and_idle_clocks(self):
        text=(PORT/'m7_cycle_probe.c').read_text()
        self.assertIn('now-out->pendingCounter',text);self.assertIn('now-out->lastTxCounter',text)
        self.assertIn('!previousPending',text)
    def test_one_shot_and_static_mailbox(self):
        text=(APP/'rk3572_powerlink_app.c').read_text()
        self.assertIn('static M7CycleProbeResult cycleResult;',text)
        self.assertIn('static M7CycleProbeResult cycleOut;',text)
        self.assertIn('cycle-consumed',text);self.assertIn('cycle-unavailable',text)
        header=(APP/'rk3572_powerlink_app.h').read_text().split('} M7PowerlinkSnapshot;',1)[0]
        self.assertNotIn('M7CycleProbeResult cycle',header)
    def test_failure_does_not_recover(self):
        failure=(PORT/'m7_cycle_probe.c').read_text().split('unsafe:',1)[1]
        for call in ('m7_mn_stop(', 'm7_mn_exit(', 'edrvcyclic_stopCycle(', 'oplk_execNmtCommand('):self.assertNotIn(call,failure)
        self.assertIn('context(out->owner)',failure)
    def test_ordered_drain_before_switch_off(self):
        source=(PORT/'m7_cycle_probe.c').read_text()
        self.assertLess(source.index('edrvcyclic_stopCycle(FALSE)'),source.index('oplk_execNmtCommand(kNmtEventSwitchOff)'))
        self.assertIn('life->tx+out->pending!=total',source);self.assertIn('m7_hrestimer_pending()',source)
    def test_real_production_guard_not_host_marking(self):
        source=(STAGE/'tests/test_powerlink_cycle_probe.c').read_text()
        self.assertIn('result=m7_cycle_probe(&out)',source)
        self.assertNotIn('m7_plk_fault();',source)
    def test_new_shell_and_abi_fixture_exist(self):
        self.assertTrue((STAGE/'tests/run_powerlink_cycle_probe_native.sh').is_file())
        self.assertTrue((STAGE/'tests/test_powerlink_cycle_probe_abi.c').is_file())
if __name__=='__main__':unittest.main()
