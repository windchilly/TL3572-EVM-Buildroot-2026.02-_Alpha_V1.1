"""P3i source guards; not a substitute for the real native cyclic harness."""
from pathlib import Path
import unittest
STAGE = Path(__file__).resolve().parents[1]

class CycleSourceTests(unittest.TestCase):
    def test_optional_external_notification_is_not_a_timer_or_fault(self):
        source = (STAGE/'source/powerlink/port/hrestimer-rk3572.c').read_text()
        hook = source.split('void hrestimer_controlExtSyncIrq(BOOL enable)',1)[1].split('tOplkError m7_hrestimer_process',1)[0]
        self.assertIn('(void)enable;', hook)
        self.assertNotIn('m7_plk_fault()', hook)
        self.assertNotIn('m7_plk_timer_arm(', hook)

    def test_external_hardware_build_is_explicitly_rejected(self):
        source = (STAGE/'source/powerlink/port/hrestimer-rk3572.c').read_text()
        self.assertIn('#ifdef TIMER_USE_EXT_SYNC_INT\n#error ', source)

    def test_real_state_progression_not_injected(self):
        source = (STAGE/'tests/test_powerlink_cycle.c').read_text()
        self.assertIn('m7_hrestimer_interrupt()', source)
        self.assertIn('return m7_mn_process()', source)
        self.assertNotIn('nmtu_postNmtEvent(', source)
        self.assertNotIn('nmtk_process(', source)

    def test_no_board_or_application_command_added(self):
        source = (STAGE/'build/build_m7_powerlink_cycle.sh').read_text()
        self.assertNotIn('mcsctl', source)
        self.assertNotIn('ssh ', source)
        self.assertNotIn('candidate.sh', source)

    def test_normal_harness_has_process_and_wall_bounds(self):
        source = (STAGE/'tests/test_powerlink_cycle.c').read_text()
        self.assertIn('i < 60000', source)
        self.assertIn('kNmtEventSwitchOff', source)
        self.assertIn('i < 32', source)
        shell = (STAGE/'tests/run_powerlink_cycle_native.sh').read_text()
        self.assertIn('timeout 20s', shell)

if __name__ == '__main__': unittest.main()
