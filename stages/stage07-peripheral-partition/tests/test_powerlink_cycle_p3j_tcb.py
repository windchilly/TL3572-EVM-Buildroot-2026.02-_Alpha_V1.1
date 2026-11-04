"""Actual retained TCB regression, local evidence ONLY. No board access."""
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
import powerlink_cycle_p3j_tcb_checks as checks
import read_powerlink_cycle_p3j_snapshot as old
from powerlink_cycle_p3j_checks import validate_snapshot,match_replies,match_heap
sys.path.pop(0)
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
IMAGE=STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf'
def fixture():
    report=json.loads((EVIDENCE/'retained-private.json').read_text())
    return report,[bytearray.fromhex(x['raw_hex']) for x in report['threads_raw']],old.image_symbols(IMAGE)

class P3jActualTcbTests(unittest.TestCase):
    def test_actual_direct_and_pthread_tasks(self):
        report,records,symbols=fixture()
        found=checks.validate_threads(records,symbols,report['cycle']['owner'])
        self.assertEqual(sorted((v['name'],v['allocated_stack']) for v in found),
            [('PLKowner',32768),('rpmsg_listen_task',4096),('rpmsg_tty_task',4096)])
        self.assertEqual(next(x for x in found if x['name']=='PLKowner')['id'],6)
    def test_actual_worker_entry_is_not_arg0(self):
        _,records,symbols=fixture()
        self.assertEqual(struct.unpack_from('<Q',records[6],32)[0],symbols['Worker'][0])
        self.assertEqual(struct.unpack_from('<Q',records[6],48)[0],0)
        self.assertNotIn(symbols['Worker'][0],[struct.unpack_from('<Q',r,48)[0] for r in records])
    def test_original_reader_reproduces_false_negative_on_actual_records(self):
        report,records,symbols=fixture()
        values=dict(snapshot=bytes.fromhex(report['snapshot_hex']),cycleResult=bytes.fromhex(report['cycle_hex']),
            cycleReady=struct.pack('<I',1),cycleAttempted=struct.pack('<I',1),g_ethLease=bytes(4),g_excInfoInternal=bytes(520),
            ownerTask=struct.pack('<I',6),g_tskCbArray=struct.pack('<Q',report['tcb_pointer']),
            g_tskMaxNum=struct.pack('<I',report['tcb_maximum']))
        values.update({k:struct.pack('<Q',v) for k,v in report['heap']['scalars'].items()})
        memory=SimpleNamespace(read_reserved_dram=lambda address,size:bytes(records[(address-report['tcb_pointer'])//800]))
        common=SimpleNamespace(confirm_up_cpus_off=Mock())
        with patch.dict(sys.modules,{'run_can_direct_pair':common,'integrated_mmu_resources':memory}), \
                patch.object(old,'private_reader',return_value=lambda name:values[name]), \
                self.assertRaisesRegex(RuntimeError,'actual RPMsg/PLKowner stacks changed/missing'):
            old.read_stopped(IMAGE)
        common.confirm_up_cpus_off.assert_called_once()
    def test_owner_wrong_entry_cannot_be_faked_in_args(self):
        _,records,symbols=fixture();struct.pack_into('<Q',records[6],32,0);struct.pack_into('<Q',records[6],48,symbols['Worker'][0])
        with self.assertRaises(ValueError):checks.validate_threads(records,symbols,6)
    def test_pthread_routine_requires_actual_wrapper(self):
        _,records,symbols=fixture();struct.pack_into('<Q',records[8],32,0)
        with self.assertRaises(ValueError):checks.validate_threads(records,symbols,6)
    def test_owner_stack_geometry_sp_args_id_failures(self):
        for offset,fmt,value in ((16,'I',4096),(20,'I',7),(24,'Q',1),(0,'Q',0),(48,'Q',1)):
            _,records,symbols=fixture();struct.pack_into('<'+fmt,records[6],offset,value)
            with self.subTest(offset=offset),self.assertRaises(ValueError):checks.validate_threads(records,symbols,6)
    def test_pthread_stack_and_sp_failures(self):
        for offset,fmt,value in ((16,'I',32768),(0,'Q',0),(24,'Q',1),(48,'Q',0)):
            _,records,symbols=fixture();struct.pack_into('<'+fmt,records[8],offset,value)
            with self.subTest(offset=offset),self.assertRaises(ValueError):checks.validate_threads(records,symbols,6)
    def test_duplicate_or_missing_records_rejected(self):
        for action in ('duplicate','missing','short'):
            _,records,symbols=fixture()
            if action=='duplicate':records.append(records[6])
            elif action=='missing':records.pop(8)
            else:records[6]=bytes(79)
            with self.subTest(action=action),self.assertRaises(ValueError):checks.validate_threads(records,symbols,6)
    def test_actual_compilers_and_candidate_library_match(self):
        proof=json.loads((EVIDENCE/'tcb-abi.json').read_text())
        old_proof=json.loads((STAGE/'tests/powerlink-cycle-p3j-runner-20261104/p3j-abi.json').read_text())
        self.assertIs(proof['passed'],True)
        self.assertEqual(proof['native'],checks.TCB_LAYOUT);self.assertEqual(proof['aarch64'],checks.TCB_LAYOUT)
        self.assertEqual(proof['candidate_sha256'],old_proof['candidate_sha256'])
        self.assertEqual(proof['source_sha256']['demos/rk3572_mica/libs/libRK3572.a'],old_proof['rtos_archive_sha256'])
    def test_actual_completion_proof_survives_only_posthoc_gate(self):
        report,records,symbols=fixture();result=json.loads((EVIDENCE/'board-result.json').read_text())
        decoded=validate_snapshot(bytes.fromhex(report['snapshot_hex']),bytes.fromhex(report['cycle_hex']),1,1)
        match_replies(decoded,result['completion']['owner'],result['completion']['result'])
        comparison=match_heap(result['heap_before'],report['heap'])
        self.assertEqual(comparison['peak_bytes'],543648);self.assertEqual(comparison['used_delta_bytes'],1064)
        self.assertEqual(decoded['lifecycle']['tx'],376)
        checks.validate_threads(records,symbols,decoded['cycle']['owner'])
        self.assertIs(result['passed'],False);self.assertIs(result['cleanup'],False)
        self.assertIsNone(result['private_stopped'])  # Do not rewrite the original failure.
if __name__=='__main__':unittest.main()
