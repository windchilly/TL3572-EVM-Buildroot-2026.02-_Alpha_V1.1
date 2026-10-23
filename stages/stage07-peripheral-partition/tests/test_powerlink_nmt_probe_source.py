"""P3g source safety/reproduction gates; native tests execute the real stack."""
from pathlib import Path
import re
import subprocess
import unittest
STAGE = Path(__file__).resolve().parents[1]
PORT = STAGE / 'source/powerlink/port'
APP = STAGE / 'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'

class NmtProbeSourceTests(unittest.TestCase):
    def test_exact_two_commands_no_run_api(self):
        source = (PORT / 'm7_nmt_probe.c').read_text()
        self.assertEqual(re.findall(r'oplk_execNmtCommand\((\w+)\)', source),
                         ['kNmtEventSwReset', 'kNmtEventSwitchOff'])
        for name in ('oplk_triggerMnStateChange', 'oplk_sendAsyncFrame', 'edrv_sendTxBuffer',
                     'kNmtEventStartNode', 'malloc(', 'socket('): self.assertNotIn(name, source)
        self.assertNotIn('oplk_execNmtCommand', (PORT / 'm7_mn.c').read_text())

    def test_bounded_transitions_not_active_before_off_and_destroy(self):
        source = (PORT / 'm7_nmt_probe.c').read_text()
        self.assertIn('#define M7_NMT_PROBE_LIMIT 32U', (PORT / 'm7_nmt_probe.h').read_text())
        self.assertIn('while (out->resetLoops < M7_NMT_PROBE_LIMIT)', source)
        self.assertIn('while (out->offLoops < M7_NMT_PROBE_LIMIT)', source)
        self.assertEqual(source.count('>= 1000U'), 2)
        self.assertLess(source.index('if (!out->reached)'), source.index('oplk_execNmtCommand(kNmtEventSwitchOff)'))
        self.assertLess(source.index('if (life->final.nmtState != kNmtGsOff)'), source.index('m7_mn_stop()'))
        self.assertEqual(source.count('m7_mn_stop()'), 1)

    def test_terminal_no_unsafe_retry_or_free(self):
        source = (PORT / 'm7_nmt_probe.c').read_text().split('unsafe:', 1)[1]
        self.assertIn('m7_plk_fault(); return life->result = result', source)
        for name in ('m7_mn_stop(', 'm7_mn_exit(', 'free(', 'entered = 0'): self.assertNotIn(name, source)

    def test_no_tx_and_real_stop_proofs(self):
        source = (PORT / 'm7_nmt_probe.c').read_text()
        for name in ('dma->tx[i].d[word]', '!out->txDescriptors', '!timer.interrupts && !timer.callbacks',
                     'quietTimer(&life->timerInitial, &life->timerFinal)', 'life->stopped.macIrq',
                     'life->stopped.dmaIrq', 'm7_eth2_hw_lease()', 'm7_hrestimer_active()'):
            self.assertIn(name, source)

    def test_default_off_up2_cold_cache_and_static_reply(self):
        patch = (STAGE / 'source/patches/uniproton/0019-rk3572-powerlink-nmt-probe.patch').read_text()
        self.assertIn('diagnostic" OFF)', patch)
        self.assertIn('NOT M7_POWERLINK_MN_PROBE', patch)
        self.assertIn('NOT MCS_CLIENT_CPU_ID STREQUAL "5"', patch)
        source = (APP / 'rk3572_powerlink_app.c').read_text()
        self.assertIn('command == NMT_PROBE && snapshot.mn.state != M7_MN_COLD', source)
        self.assertIn('if (!probe.lifecycle.clean)', source)
        self.assertIn('static M7PowerlinkSnapshot out;', source)
        init = source.split('uint32_t Rk3572PowerlinkInit(void)')[1].split('static int matches')[0]
        self.assertNotIn('m7_nmt_probe(', init)

    def test_pdo_error_and_no_wait_patch(self):
        source = (PORT / '0006-uniproton-pdo-setup-no-wait.patch').read_text()
        self.assertIn('+    ret = pdoucal_postSetupPdoBuffers', source)
        self.assertIn('+    if (ret != kErrorOk)', source)
        self.assertIn('+    if (pdokcalmem_pPdo_g == NULL)', source)
        self.assertIn('+        return kErrorNoResource;', source)
        self.assertEqual(source.count('+#if defined(OPLK_TARGET_UNIPROTON)'), 2)
        self.assertIn('     target_msleep(CONFIG_PDO_SETUP_WAIT_TIME);', source)

    def test_cyclic_null_guards_and_patches_parse(self):
        source = (PORT / '0007-uniproton-cyclic-allocation-guards.patch').read_text()
        self.assertEqual(source.count('+        return kErrorEdrvNoFreeBufEntry;'), 3)
        for patch in (PORT / '0006-uniproton-pdo-setup-no-wait.patch',
                      PORT / '0007-uniproton-cyclic-allocation-guards.patch',
                      STAGE / 'source/patches/uniproton/0019-rk3572-powerlink-nmt-probe.patch'):
            result = subprocess.run(['git', 'apply', '--numstat', str(patch)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rebuild_and_final_audit_hooks(self):
        build = (STAGE / 'build/build_m7_powerlink_nmt.sh').read_text()
        for name in ('0006-', '0007-', 'cmake --build', '--whole-archive'): self.assertIn(name, build)
        build = (STAGE / 'build/build_m7_powerlink_nmt_probe_candidate.sh').read_text()
        self.assertIn('--reverse --check', build)
        self.assertIn('audit_powerlink_nmt_probe.py', build)
        audit = (STAGE / 'tests/audit_powerlink_nmt_probe.py').read_text()
        self.assertIn('audit_powerlink_mn_probe.py', audit)
        self.assertIn('hardware_tested=False', audit)

if __name__ == '__main__': unittest.main()
