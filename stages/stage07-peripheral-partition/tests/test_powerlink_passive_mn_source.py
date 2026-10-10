"""P3a source/negative-boundary checks, not hardware acceptance."""
from pathlib import Path
import unittest
from unittest.mock import patch
import audit_powerlink_passive_mn as audit

STAGE = Path(__file__).resolve().parents[1]
PORT = STAGE / "source/powerlink/port"


class PassiveMnTests(unittest.TestCase):
    def test_no_runtime_start_or_arbitrary_send_api(self):
        source = (PORT / "m7_mn.c").read_text()
        for forbidden in ("oplk_execNmtCommand", "edrv_sendTxBuffer", "kNmtEventSwReset",
                          "socket(", "system(", "fopen("):
            self.assertNotIn(forbidden, source)
        header = (PORT / "m7_mn.h").read_text()
        self.assertNotIn("m7_mn_start", header)

    def test_entry_gate_and_owner_serialized_pump(self):
        source = (PORT / "m7_mn.c").read_text()
        pump = source.split("uint32_t m7_mn_process(void)", 1)[1].split("uint32_t m7_mn_stop", 1)[0]
        self.assertIn("!owner()", pump)
        self.assertIn("!m7_plk_ready()", pump)
        self.assertLess(pump.index("m7_hrestimer_process()"), pump.index("m7_edrv_poll(8)"))
        self.assertLess(pump.index("m7_edrv_poll(8)"), pump.index("oplk_process()"))
        self.assertNotIn("TaskDelay", pump)

    def test_stop_preflight_before_any_stack_free(self):
        source = (PORT / "0003-uniproton-passive-lifecycle.patch").read_text()
        preflight = source.split("ctrlu_shutdownStack(void)", 1)[1]
        self.assertLess(preflight.index("ret = edrv_exit()"), preflight.index("ctrlInstance_l.fInitialized = FALSE"))
        self.assertLess(preflight.index("ret = hrestimer_exit()"), preflight.index("ctrlInstance_l.fInitialized = FALSE"))
        self.assertEqual(preflight.count("+        return ret;"), 2)
        self.assertIn("+    ret = target_init();", source)
        self.assertIn("+        ctrlu_exit();", source)

    def test_terminal_partial_failure_keeps_resources(self):
        source = (PORT / "m7_mn.c").read_text()
        fault = source.split("static uint32_t fault(", 1)[1].split("static tOplkError event", 1)[0]
        self.assertIn("M7_MN_FAULT", fault)
        for forbidden in ("oplk_destroy", "oplk_exit", "free(", "memset("):
            self.assertNotIn(forbidden, fault)

    def test_old_phase_inputs_not_patched(self):
        source = (STAGE / "build/build_m7_powerlink_passive_mn.sh").read_text()
        self.assertIn('POWERLINK_BUILD_ROOT="$output/p2"', source)
        self.assertIn('prepare_m7_powerlink.py" "$output/source"', source)
        for old in ("build_m7_powerlink_core.sh", "build_m7_powerlink_edrv.sh", "build_m7_powerlink_rtos.sh"):
            self.assertNotIn("0003", (STAGE / "build" / old).read_text())

    def test_audit_rejects_missing_core_od_and_proxy(self):
        required = audit.HAL | {"oplk_create", "oplk_process", "oplk_destroy", "obdcreate_initObd",
                               "m7_mn_initialize", "m7_mn_prepare", "m7_mn_process", "m7_mn_stop", "m7_mn_exit"}
        boundary = audit.LIBC | audit.BSP | audit.PLATFORM
        cases = [(required - {"obdcreate_initObd"}, boundary),
                 (required - {"hrestimer_init"}, boundary),
                 (required, boundary | {"socket"}), (required, boundary | {"__aarch64_ldadd4_relax"})]
        for defined, undefined in cases:
            lines = [f"00000000 T {x}" for x in defined] + [f" U {x}" for x in undefined]
            with patch.object(audit.subprocess, "check_output", return_value="\n".join(lines)):
                with self.assertRaises(ValueError):
                    audit.audit(Path("not-read"), Path("fake-toolchain"))

    def test_all_four_request_queue_errors_propagated(self):
        source = (PORT / "0005-mn-request-queue-allocation-errors.patch").read_text()
        self.assertEqual(source.count("+        ret = kErrorNoResource;"), 4)
        cfg = (PORT / "mn/CMakeLists.txt").read_text()
        self.assertIn("foreach(position RANGE 1 16)", cfg)
        self.assertIn("-include common/oplkinc.h", cfg)


if __name__ == "__main__":
    unittest.main()
