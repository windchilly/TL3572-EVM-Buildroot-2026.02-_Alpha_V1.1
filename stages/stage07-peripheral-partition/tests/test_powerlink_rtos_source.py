"""P2 fail-closed source/config tests. These are not hardware timing tests."""
from pathlib import Path
import unittest
from unittest.mock import patch
import audit_powerlink_rtos as audit

STAGE = Path(__file__).resolve().parents[1]
PORT = STAGE / "source/powerlink/port"
BSP = STAGE / "source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_powerlink_rtos.c"


class RtosBoundaryTests(unittest.TestCase):
    def test_dependency_sets_do_not_admit_proxy(self):
        for symbol in ("pthread_create", "socket", "pcap_dispatch", "PRT_HwiDelete", "PRT_HwiDisable", "__aarch64_ldadd4_acq_rel"):
            self.assertNotIn(symbol, audit.PLATFORM | audit.RTOS | audit.LIBC)

    def test_tick_and_other_ppis_not_written(self):
        text = BSP.read_text().lower()
        self.assertIn("#define plk_ppi 30u", text)
        self.assertNotIn("msr cntv", text)
        self.assertNotIn("msr cntfrq", text)
        self.assertNotIn("writegic(0x0,", text)
        self.assertIn("writegic(0x180, plk_bit)", text)
        self.assertIn("writegic(0x280, plk_bit)", text)

    def test_real_cache_ops_and_context_check(self):
        text = BSP.read_text()
        for token in ("dc cvac", "dc civac", "ctr_el0", "OS_FLG_HWI_ACTIVE", "OS_FLG_TICK_ACTIVE",
                      "OS_FLG_SYS_ACTIVE", "OS_FLG_EXC_ACTIVE", "defined(OS_OPTION_SMP)"):
            self.assertIn(token, text)
        self.assertIn("m7_plk_cache_range(begin, length)", text)

    def test_isr_has_no_stack_callback(self):
        timer = (PORT / "hrestimer-rk3572.c").read_text()
        isr = timer.split("void m7_hrestimer_interrupt(void)", 1)[1].split("static Timer*", 1)[0]
        self.assertNotIn("callback", isr)
        self.assertNotIn("edrv", isr)
        self.assertIn("m7_plk_timer_mask()", isr)

    def test_candidate_default_off_up2_only_and_no_run_command(self):
        text = (STAGE / "source/patches/uniproton/0012-rk3572-powerlink-rtos-dormant.patch").read_text()
        self.assertIn('target/timer" OFF)', text)
        self.assertIn('MCS_CLIENT_CPU_ID STREQUAL "5"', text)
        command = (STAGE / "source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_integrated_command.h").read_text()
        self.assertNotIn("powerlink", command.lower())

    def test_audit_rejects_missing_hal_and_proxy(self):
        # Fail at the symbol boundary, before reading/writing any files.
        good = [f"00000000 T {name}" for name in audit.HAL]
        bad_cases = [good[:-1] + [f" U {name}" for name in audit.LIBC | audit.BSP | audit.PLATFORM],
                     good + [f" U {name}" for name in audit.LIBC | audit.BSP | audit.PLATFORM | {"socket"}]]
        for lines in bad_cases:
            with patch.object(audit.subprocess, "check_output", return_value="\n".join(lines)):
                with self.assertRaises(ValueError):
                    audit.audit(Path("not-read.o"), Path("fake-toolchain"), False)


if __name__ == "__main__":
    unittest.main()
