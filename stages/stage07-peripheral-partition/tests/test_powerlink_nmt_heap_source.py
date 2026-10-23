"""Offline P3h scope/guard regressions; actual C behavior is native-tested."""
from pathlib import Path
import unittest
STAGE = Path(__file__).resolve().parents[1]
class NmtHeapSourceTests(unittest.TestCase):
    def test_heap_default_off_and_up2_only(self):
        text = (STAGE / 'source/patches/uniproton/0020-rk3572-powerlink-nmt-heap.patch').read_text(encoding='utf-8')
        self.assertIn('1MiB FSC heap" OFF)', text)
        self.assertIn('NOT M7_POWERLINK_NMT_PROBE OR NOT MCS_CLIENT_CPU_ID STREQUAL "5"', text)
        self.assertIn('#define OS_MEM_FSC_PT_SIZE                              0x100000', text)
        self.assertIn('#define OS_MEM_FSC_PT_SIZE                              0x80000', text)
    def test_budget_is_full_od_not_channel_reduction(self):
        text = (STAGE / 'source/powerlink/port/mn/CMakeLists.txt').read_text()
        self.assertIn('NMT_MAX_NODE_ID=254', text)
        patch = (STAGE / 'source/patches/uniproton/0020-rk3572-powerlink-nmt-heap.patch').read_text(encoding='utf-8')
        self.assertNotIn('NMT_MAX_NODE_ID', patch)
        self.assertNotIn('objdicts/', patch)
    def test_critical_and_process_preserve_first_code(self):
        text = (STAGE / 'source/powerlink/port/m7_mn.c').read_text()
        self.assertIn('if (status.lastError == kErrorOk) status.lastError = (uint32_t)error;', text)
        self.assertIn('if (status.lastError == kErrorOk) status.lastError = (uint32_t)arg->internalError.oplkError;', text)
        self.assertIn('return status.lastError;', text)
    def test_real_stack_budget_regression(self):
        text = (STAGE / 'tests/test_powerlink_nmt_probe.c').read_text()
        self.assertIn('heap_small', text); self.assertIn('heap_full', text)
        self.assertIn('out.lifecycle.stackError == kErrorPdoInitError', text)
        self.assertIn('out.lifecycle.final.lastError == kErrorPdoInitError', text)
        self.assertIn('heapUsed == reserve && !budgetFailures', text)
    def test_final_audit_checks_actual_config_and_pool(self):
        text = (STAGE / 'tests/audit_powerlink_nmt_heap.py').read_text()
        self.assertIn('up2_fsc=0x100000', text)
        self.assertIn("/config/prt_config.c", text)
        self.assertIn("'#define OS_MEM_FSC_PT_SIZE 0x100000'", text)
        self.assertIn('stack_audit(assembly)', text)
        self.assertIn('lse_instructions(assembly)', text)
    def test_build_does_not_deploy(self):
        text = (STAGE / 'build/build_m7_powerlink_nmt_heap_candidate.sh').read_text()
        for forbidden in ('ssh ', 'mcsctl', '/etc/mica', 'reboot', '/dev/mem'):
            self.assertNotIn(forbidden, text)
        self.assertIn('M7_POWERLINK_NMT_HEAP:BOOL=ON', text)
if __name__ == '__main__': unittest.main()
