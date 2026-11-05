"""P4a strict structural CDC audit tests. No network or board imports."""
from pathlib import Path
import json
import struct
import tempfile
import unittest
STAGE=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(STAGE/'build'))
import inspect_m7_powerlink_cdc as audit
import build_m7_powerlink_linux_cn as builder
sys.path.pop(0)

def cdc(*entries):
    return struct.pack('<I',len(entries))+b''.join(struct.pack('<HBI',index,sub,len(data))+data for index,sub,data in entries)

class CdcIntakeTests(unittest.TestCase):
    def test_pinned_baseline_is_still_no_cn(self):
        report=audit.baseline_report()
        self.assertFalse(report['cn_capable'] or report['runtime_ready'] or report['board_contacted'])
        self.assertTrue(all(report['baseline_checks'].values()))
        self.assertEqual(report['builtin_cdc']['entries'][0]['cycle_us'],1000)
    def test_short_count_header(self):
        for data in (b'',b'\1',b'\1\0\0'):
            with self.assertRaises(ValueError):audit.inspect_cdc(data)
    def test_zero_count_rejected(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(bytes(4))
    def test_count_policy_limit(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(struct.pack('<I',audit.MAX_ENTRIES+1))
    def test_size_policy_limit(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(bytes(audit.MAX_BYTES+1))
    def test_truncated_entry_header(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(struct.pack('<I',1)+bytes(6))
    def test_truncated_entry_value(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(struct.pack('<IHBI',1,0x1006,0,4)+bytes(3))
    def test_zero_length_strict_subset_rejected(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(cdc((0x2000,0,b'')))
    def test_trailing_data_strict_subset_rejected(self):
        with self.assertRaises(ValueError):audit.inspect_cdc(cdc((0x1006,0,b'\xe8\3\0\0'))+b'\0')
    def test_order_and_duplicate_writes_preserved(self):
        report=audit.inspect_cdc(cdc((0x1600,0,b'\0'),(0x1600,1,bytes(8)),(0x1600,0,b'\1')))
        self.assertEqual([(x['sequence'],x['subindex'],x['data_hex']) for x in report['entries']],[(0,0,'00'),(1,1,'00'*8),(2,0,'01')])
    def test_mn_scope_only_decodes_cfmdomain(self):
        data=cdc((0x1f22,1,cdc((0x1006,0,b'\xe8\3\0\0'))))
        report=audit.inspect_cdc(data,'mn');child=report['entries'][0]['cn_concise_config']
        self.assertEqual(child['scope'],'cn');self.assertEqual(child['entries'][0]['cycle_us'],1000)
        self.assertNotIn('cn_concise_config',audit.inspect_cdc(data)['entries'][0])
        self.assertFalse(child['device_semantics_validated'] or child['runtime_ready'])
    def test_cn_scope_never_guesses_nested_domains(self):
        report=audit.inspect_cdc(cdc((0x1f22,1,b'opaque device bytes')),'cn')
        self.assertNotIn('cn_concise_config',report['entries'][0])
        with self.assertRaises(ValueError):audit.inspect_cdc(b'1234','device')
    def test_assignment_is_raw_not_automatic_configuration(self):
        report=audit.inspect_cdc(cdc((0x1f81,7,b'\7\0\0\x80')),'mn')
        self.assertEqual(report['entries'][0]['node_assignment_raw'],'0x80000007')
        self.assertFalse(report['runtime_ready'])
    def test_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report.json';audit.write_report(path,{'runtime_ready':False});original=path.read_bytes()
            with self.assertRaises(FileExistsError):audit.write_report(path,{'runtime_ready':True})
            self.assertEqual(path.read_bytes(),original)

class LinuxPeerPreparationTests(unittest.TestCase):
    def test_build_destination_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(FileExistsError):builder.build(Path(directory))
    def test_build_script_does_not_run_peer_or_board(self):
        source=(STAGE/'build/build_m7_powerlink_linux_cn.py').read_text()
        self.assertNotIn('ssh',source);self.assertNotIn('socket(',source)
        self.assertNotIn("run(str(binary)",source)
        self.assertIn('qcD <TARGET>',source);self.assertIn(' -D <TARGET>',source)
        self.assertIn('CFG_USE_PCAP_EDRV=OFF',source)
    def test_patch_is_linux_cn_only(self):
        source=(STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch').read_text()
        paths=[line for line in source.splitlines() if line.startswith('diff --git')]
        self.assertEqual(len(paths),2)
        self.assertTrue(all('/liboplkcn/' in path or '/demo_cn_console/' in path for path in paths))
    def test_template_is_not_a_device_configuration(self):
        data=json.loads((STAGE/'config/powerlink-cn-intake.template.json').read_text())
        self.assertIs(data['runtime_ready'],False)
        self.assertIsNone(data['cn']['node_id']);self.assertIsNone(data['requested_cycle_us'])

if __name__=='__main__':unittest.main()
