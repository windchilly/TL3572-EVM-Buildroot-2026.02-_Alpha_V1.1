"""Actual v2 evidence parsing/tamper regression, entirely offline."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from verify_powerlink_cycle_p3j_v2_hw_checkpoint import EVIDENCE,hardware_evidence

class ActualV2Tests(unittest.TestCase):
    def check(self,directory):
        with contextlib.redirect_stdout(io.StringIO()):return hardware_evidence(directory)
    def reject(self,name,change):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'evidence';shutil.copytree(EVIDENCE,root,ignore=shutil.ignore_patterns('__pycache__'))
            path=root/name;data=json.loads(path.read_text());change(data);path.write_text(json.dumps(data))
            with self.assertRaises((ValueError,RuntimeError)):self.check(root)
    def test_actual_success(self):
        report=self.check(EVIDENCE)
        self.assertTrue(report['passed'] and report['automatic_linux_return'])
        self.assertEqual((report['tx'],report['timer_irqs'],report['timer_callbacks']),(376,376,376))
        self.assertEqual(report['heap']['peak_headroom_bytes'],504896)
    def test_failed_or_retained_is_not_accepted(self):
        self.reject('board-result.json',lambda x:x.update(cleanup=False))
    def test_wrong_upload_is_not_accepted(self):
        self.reject('board-input-sha256.json',lambda x:x['files'].pop('tcb-abi.json'))
    def test_tcb_entry_cannot_change(self):
        def corrupt(x):
            records=x['private_stopped']['tcb_prefix_hex'];raw=bytearray.fromhex(records[6]);raw[32:40]=bytes(8);records[6]=raw.hex()
        self.reject('board-result.json',corrupt)
    def test_raw_publication_cannot_change(self):
        self.reject('board-result.json',lambda x:x['private_stopped'].update(cycle_sha256='0'*64))
    def test_postflight_drift_is_not_accepted(self):
        self.reject('postflight.json',lambda x:x.update(hold=True))
    def test_formal_file_drift_is_not_accepted(self):
        self.reject('post-file-sha256.json',lambda x:x['files']['/lib/firmware/rk3572-uniproton-up-b.elf'].update(sha256='0'*64))

if __name__=='__main__':unittest.main()
