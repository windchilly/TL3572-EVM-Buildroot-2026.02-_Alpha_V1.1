"""P3b command/boot boundaries; native tests exercise actual core separately."""
from pathlib import Path
import unittest
from audit_powerlink_owner import check_simd
STAGE = Path(__file__).resolve().parents[1]
APP = STAGE / "source/overlay/uniproton/demos/rk3572_mica/apps/openamp"


class OwnerSourceTests(unittest.TestCase):
    def test_no_new_simd_against_fixed_baseline(self):
        old = "000000007c201000 <metal_io_init>:\n 7c201004: 4f00041f movi v31.4s, #0x0\n"
        moved = "000000007c202000 <metal_io_init>:\n 7c202004: 4f00041f movi v31.4s, #0x0\n"
        self.assertEqual(len(check_simd(moved, old)), 1)
        for invalid in (moved.replace("metal_io_init", "PLKowner"), moved.replace("4f00041f", "4f00043f"),
                        moved.replace("7c202004", "7c202008")):
            with self.assertRaises(ValueError): check_simd(invalid, old)
        with self.assertRaises(ValueError):
            check_simd(moved.replace("4f00041f", "4f00043f"), old,
                       {("metal_io_init", 4): ((1, b"old"), (1, b"new"))})

    def test_no_hardware_or_network_entrypoints(self):
        text = (APP / "rk3572_powerlink_app.c").read_text()
        for name in ("m7_mn_prepare(", "m7_mn_process(", "m7_mn_stop(", "oplk_execNmtCommand",
                     "edrv_sendTxBuffer", "m7_plk_timer_acquire(", "m7_eth2_hw_acquire("):
            self.assertNotIn(name, text)
        boot = text.split("uint32_t Rk3572PowerlinkInit(void)")[1].split("static int matches")[0]
        self.assertNotIn("m7_mn_initialize(", boot)

    def test_owner_and_bounded_record(self):
        text = (APP / "rk3572_powerlink_app.c").read_text()
        for check in ("task == ownerTask", "length > 48", "snapshot.pending || snapshot.running",
                      "snapshot.submitted == UINT32_MAX", "snapshot.mn.state != M7_MN_IDLE"):
            self.assertIn(check, text)
        self.assertNotIn("malloc(", text)
        self.assertNotIn("oplk/", text)

    def test_final_full_object_not_gc(self):
        text = (STAGE / "source/patches/uniproton/0013-rk3572-powerlink-owner-dormant.patch").read_text()
        self.assertIn('option(M7_POWERLINK_MN "Dormant UP2 MN owner, software commands only" OFF)', text)
        self.assertIn("--no-gc-sections", text)
        self.assertIn("list(REMOVE_ITEM SRC", text)
        self.assertIn('target_sources(${APP} PRIVATE "${M7_POWERLINK_OBJECT}")', text)

    def test_up1_denial_and_optional_hook(self):
        text = (APP / "rk3572_integrated.c").read_text()
        self.assertIn("#if defined(M7_POWERLINK_MN) && (MCS_CLIENT_CPU_ID == 5)", text)
        self.assertIn("PLK UP1 ERROR owned-by-UP2", text)
        self.assertIn("return Rk3572PowerlinkInput(data, length)", text)


if __name__ == "__main__":
    unittest.main()
