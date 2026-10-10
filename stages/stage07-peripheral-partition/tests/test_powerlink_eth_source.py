from pathlib import Path
import unittest
STAGE = Path(__file__).resolve().parents[1]
PORT = STAGE / 'source/powerlink/port'
APP = STAGE / 'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'

class EthProbeSourceTests(unittest.TestCase):
    def test_no_stack_timer_dma(self):
        text = (PORT / 'm7_eth_probe.c').read_text()
        for name in ('oplk_', 'm7_mn_', 'edrv_', 'hw_start(', 'hw_write(', 'hrestimer_', 'memcpy(', 'malloc('):
            self.assertNotIn(name, text)
        self.assertEqual(text.count('m7_eth2_hw_probe_stop('), 1)
        self.assertIn('out->clean = acquired == 0 && !out->leaseAfter', text)
        self.assertIn('if (out->leaseAfter) { out->clean = 0;', text)

    def test_bsp_no_start_bits_or_descriptors(self):
        text = (APP / 'rk3572_eth_test.c').read_text().split('int m7_eth2_hw_probe_mode(')[1].split('\n#endif')[0]
        self.assertIn('Set(0U, (1U << 15) | (1U << 14));', text)
        for name in ('g_dma', 'memset(', 'hw_start(', 'Set(0x1104', 'Set(0x1108', 'Set(0x1120', 'Set(0x1128'):
            self.assertNotIn(name, text)
        self.assertEqual(text.count('Mdio(1U, &out->bmsr, 0)'), 2)

    def test_stop_retains_lease_on_readback_failure(self):
        text = (APP / 'rk3572_eth_test.c').read_text().split('static int PowerlinkStop(')[1].split('int m7_eth2_hw_stop(')[0]
        self.assertLess(text.index('UNSAFE stop readback'), text.index('__atomic_store_n(&g_ethLease, 0U'))
        self.assertIn('out->dma = Reg(0x1000U)', text)

    def test_default_off_cold_only(self):
        patch = (STAGE / 'source/patches/uniproton/0015-rk3572-powerlink-eth-probe.patch').read_text()
        self.assertIn('option(M7_POWERLINK_ETH_PROBE "Explicit UP2 PHY/MAC diagnostic without DMA or frames" OFF)', patch)
        self.assertIn('NOT MCS_CLIENT_CPU_ID STREQUAL "5"', patch)
        text = (APP / 'rk3572_powerlink_app.c').read_text()
        self.assertIn('command == ETH_PROBE && snapshot.mn.state != M7_MN_COLD', text)
        self.assertIn('if (!eth.clean)', text)
        boot = text.split('uint32_t Rk3572PowerlinkInit(void)')[1].split('static int matches')[0]
        self.assertNotIn('m7_eth_probe(', boot)

    def test_header_pure(self):
        header = (PORT / 'm7_eth_probe.h').read_text()
        self.assertNotIn('oplk/', header)
        self.assertNotIn('prt_', header)
        self.assertIn('M7EthProbeResult', header)

if __name__ == '__main__': unittest.main()
