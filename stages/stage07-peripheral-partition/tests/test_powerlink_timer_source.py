from pathlib import Path
import unittest
STAGE = Path(__file__).resolve().parents[1]
PORT = STAGE / "source/powerlink/port"
APP = STAGE / "source/overlay/uniproton/demos/rk3572_mica/apps/openamp"


class TimerSourceTests(unittest.TestCase):
    def test_probe_no_ethernet_mn(self):
        text = (PORT / "m7_timer_probe.c").read_text()
        for name in ("oplk_initialize(", "oplk_create(", "m7_mn_prepare(", "edrv_", "m7_eth2_hw_"):
            self.assertNotIn(name, text)
        self.assertIn("stats.interrupts != previous + 1U", text)
        self.assertIn("result = M7_TIMER_NO_IRQ; goto cleanup", text)
        self.assertLess(text.index("stats.interrupts != previous + 1U"), text.index("m7_hrestimer_process()"))

    def test_bounds_and_safe_cleanup(self):
        text = (PORT / "m7_timer_probe.c").read_text()
        for check in ("round < 3", "sample < 8", "20000000U", "spins == 10000000U", "target_cleanup()"):
            self.assertIn(check, text)
        self.assertIn("hrestimer_exit() != kErrorOk || target_cleanup()", text)
        self.assertIn("out->before.priority27 != out->after.priority27", text)
        self.assertIn("out->after.ticks <= out->before.ticks", text)

    def test_default_off(self):
        patch = (STAGE / "source/patches/uniproton/0014-rk3572-powerlink-timer-probe.patch").read_text()
        self.assertIn('option(M7_POWERLINK_TIMER_PROBE "Explicit UP2 timer-only hardware diagnostic" OFF)', patch)
        self.assertIn('NOT MCS_CLIENT_CPU_ID STREQUAL "5"', patch)
        app = (APP / "rk3572_powerlink_app.c").read_text()
        self.assertIn('command == TIMER_PROBE && snapshot.mn.state != M7_MN_COLD', app)
        self.assertIn('if (!timer.clean)', app)
        boot = app.split('uint32_t Rk3572PowerlinkInit(void)')[1].split('static int matches')[0]
        self.assertNotIn('m7_timer_probe(', boot)

    def test_isr_only_measurement(self):
        text = (APP / "rk3572_powerlink_rtos.c").read_text()
        isr = text.split("static void timerIsr(")[1].split("int m7_plk_timer_acquire")[0]
        for name in ("PRT_Printf", "send_message", "callback(", "hrestimer_process", "oplk_"):
            self.assertNotIn(name, isr)
        self.assertIn("diagDeadline", isr)
        self.assertIn("#ifdef M7_POWERLINK_TIMER_PROBE", isr)

    def test_pure_header(self):
        header = (PORT / "m7_timer_probe.h").read_text()
        self.assertNotIn("oplk/", header)
        self.assertNotIn("prt_", header)
        self.assertIn("M7TimerProbeResult", header)

    def test_gic_ns_no_security_writes(self):
        text = (APP / "rk3572_powerlink_rtos.c").read_text()
        self.assertIn("m7_plk_gic_usable(readGic(4)", text)
        self.assertNotIn("!(readGic(0x80) & PLK_BIT)", text)
        self.assertNotIn("writeGic(0x80", text)
        self.assertIn("*frequency = 0; PRT_HwiRestore(state); return 1;", text)

    def test_board_command_allowlist(self):
        text = (STAGE / "tests/board/run_powerlink_timer.py").read_text()
        self.assertIn("if text not in ALLOWED", text)
        self.assertNotIn("'M7 run", text)
        self.assertNotIn("'PLK env-init'", text)
        self.assertIn("UNSAFE/UNKNOWN: retained temporary UP2", text)
        self.assertIn("baseline_seq", text)


if __name__ == "__main__": unittest.main()
