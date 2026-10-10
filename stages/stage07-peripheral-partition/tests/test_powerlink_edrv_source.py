"""P1 boundaries/config regression checks, not MMIO or PHY simulation."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("audit_edrv", Path(__file__).parent / "audit_powerlink_edrv.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
STAGE = Path(__file__).resolve().parents[1]


class EdrvBoundaryTests(unittest.TestCase):
    def test_real_edrv_boundary(self):
        AUDIT.check_boundary(AUDIT.REMAINING | AUDIT.LIBC, AUDIT.EDRV)

    def test_fake_backend_and_missing_implementation_rejected(self):
        for name in AUDIT.BSP:
            with self.subTest(name=name), self.assertRaises(ValueError):
                AUDIT.check_boundary(AUDIT.REMAINING - {name}, AUDIT.EDRV)
        for name in AUDIT.EDRV:
            with self.subTest(name=name), self.assertRaises(ValueError):
                AUDIT.check_boundary(AUDIT.REMAINING, AUDIT.EDRV - {name})

    def test_external_proxy_dependency_rejected(self):
        for name in ("socket", "sendto", "pthread_create", "pcap_dispatch", "__aarch64_cas4_acq_rel"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                AUDIT.check_boundary(AUDIT.REMAINING | {name}, AUDIT.EDRV)

    def test_unsupported_options_stay_disabled(self):
        cfg = (STAGE / "source/powerlink/port/oplkcfg.h").read_text()
        for option in ("CONFIG_DLL_DEFERRED_RXFRAME_RELEASE_SYNC", "CONFIG_DLL_DEFERRED_RXFRAME_RELEASE_ASYNC",
                       "CONFIG_EDRV_AUTO_RESPONSE_DELAY"):
            self.assertIn(f"#define {option} FALSE", cfg)

    def test_candidate_is_dormant_up2_only(self):
        patch = (STAGE / "source/patches/uniproton/0011-rk3572-powerlink-edrv-dormant.patch").read_text()
        self.assertIn('MCS_CLIENT_CPU_ID STREQUAL "5"', patch)
        self.assertIn('not MN runtime)" OFF)', patch)
        command = (STAGE / "source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_integrated_command.h").read_text()
        self.assertNotIn("powerlink", command.lower())

    def test_ring_reserves_one_and_nc_window(self):
        driver = (STAGE / "source/powerlink/port/edrv-rk3572.c").read_text()
        self.assertIn("instance.txCount == M7_ETH2_RING - 1U", driver)
        header = (STAGE / "source/powerlink/port/m7_eth2_hw.h").read_text()
        self.assertIn("0x7ca10000UL", header)
        self.assertIn("sizeof(struct M7Eth2Dma) <= 0x10000U", header)


if __name__ == "__main__":
    unittest.main()
