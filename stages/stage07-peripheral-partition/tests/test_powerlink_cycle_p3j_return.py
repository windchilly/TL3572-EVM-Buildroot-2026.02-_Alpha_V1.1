"""Stopped-only return under fake native boundaries, never connects a board."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
import return_powerlink_cycle_p3j_linux as r
from read_powerlink_cycle_p3j_snapshot import image_symbols
sys.path.pop(0)
OLD=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
SYMBOLS=image_symbols(STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf')
def baseline():
    result=json.loads((OLD/'board-result.json').read_text())
    return dict(before=json.loads(next(x[7:] for x in (OLD/'board-test.log').read_text().splitlines() if x.startswith('BEFORE '))),
        retained=json.loads((OLD/'retained-private.json').read_text()),heap_before=result['heap_before'],completion=result['completion'])

class ReturnReadProofTests(unittest.TestCase):
    def read(self,kind='normal'):
        b=baseline();old=b['retained'];order=[]
        values=dict(snapshot=bytes.fromhex(old['snapshot_hex']),cycleResult=bytes.fromhex(old['cycle_hex']),
            cycleReady=struct.pack('<I',1),cycleAttempted=struct.pack('<I',1),g_ethLease=bytes(4),g_excInfoInternal=bytes(520),
            ownerTask=struct.pack('<I',6),g_tskCbArray=struct.pack('<Q',old['tcb_pointer']),g_tskMaxNum=struct.pack('<I',old['tcb_maximum']))
        values.update({k:struct.pack('<Q',v) for k,v in old['heap']['scalars'].items()})
        if kind=='lease':values['g_ethLease']=struct.pack('<I',2)
        if kind=='heap':values['g_memUsage']=struct.pack('<Q',40000)
        if kind=='publish':b['retained']['snapshot_sha256']='changed'
        if kind=='bounds':values['g_tskMaxNum']=struct.pack('<I',64)
        def private(name):order.append(name);return values[name]
        def memory(address,size):
            order.append('TCB');self.assertEqual(size,80)
            raw=bytes.fromhex(old['threads_raw'][(address-old['tcb_pointer'])//800]['raw_hex'])
            return bytes(80) if kind=='tcb' else raw
        common=SimpleNamespace(confirm_up_cpus_off=Mock(side_effect=lambda:order.append('OFF')))
        if kind=='live':common.confirm_up_cpus_off.side_effect=RuntimeError('CPU not OFF')
        with patch.object(r,'image_symbols',return_value=SYMBOLS),patch.object(r,'private_reader',return_value=private), \
                patch.dict(sys.modules,{'integrated_mmu_resources':SimpleNamespace(read_reserved_dram=memory)}):
            if kind=='normal':report=r.read_stopped(SimpleNamespace(common=common),b)
            else:
                with self.assertRaises((RuntimeError,ValueError)):r.read_stopped(SimpleNamespace(common=common),b)
                report=None
        return report,order,common
    def test_actual_records_and_off_before_after(self):
        report,order,common=self.read()
        self.assertEqual(order[0],'OFF');self.assertEqual(order[-1],'OFF')
        self.assertEqual(report['heap_comparison']['peak_bytes'],543648)
        self.assertEqual(len(report['threads']),3);self.assertEqual(common.confirm_up_cpus_off.call_count,2)
    def test_live_cpu_prevents_private_io(self):
        _,order,_=self.read('live');self.assertEqual(order,[])
    def test_lease_heap_publication_bounds_or_tcb_refuse(self):
        for kind in ('lease','heap','publish','bounds','tcb'):
            with self.subTest(kind=kind):self.read(kind)

class ReturnActionTests(unittest.TestCase):
    def workflow(self,kind='normal'):
        calls=[];state=dict(hold=True)
        class Device:
            name='2a040000.ethernet'
        class Bind:
            def write_text(self,value):
                calls.append(('bind',value))
                if kind=='bind':raise RuntimeError('ambiguous bind')
        class Driver:
            def __truediv__(self,value):return Bind()
        class Hold:
            def __init__(self,value):pass
            def exists(self):return state['hold']
        def control(*args):
            calls.append(args)
            if kind=='rm':raise RuntimeError('ambiguous rm')
        def command(*args):
            calls.append(args)
            if args[0]=='rmmod':
                if kind=='rmmod':raise RuntimeError('ambiguous unload')
                state['hold']=False
            if args[0]=='ip' and kind=='up':raise RuntimeError('ambiguous link up')
        common=SimpleNamespace(control=control,command=command,confirm_up_cpus_off=Mock())
        def check(base,b,retained):
            calls.append(('baseline',retained))
            if kind=='baseline' or (kind=='drift' and not retained):raise RuntimeError('baseline drift')
        def claim():
            calls.append(('claim',))
            if kind=='marker':raise FileExistsError('consumed')
        with ExitStack() as stack:
            stack.enter_context(patch.object(r,'Path',Hold));stack.enter_context(patch.object(r,'check_baseline',side_effect=check))
            stack.enter_context(patch.object(r,'claim',side_effect=claim))
            stack.enter_context(patch.object(r,'read_stopped',side_effect=ValueError('bad proof') if kind=='proof' else None,return_value={'valid':True}))
            stack.enter_context(patch.object(r,'linux_full',side_effect=RuntimeError('no full link') if kind=='link' else None))
            if kind=='link':
                stack.enter_context(patch.object(r.time,'monotonic',side_effect=[0,21]))
            report=r.restore(SimpleNamespace(common=common,DRIVER=Driver(),DEVICE=Device()),{})
        return report,calls,state
    def test_success_exact_actions_no_start_stop(self):
        report,calls,state=self.workflow()
        self.assertTrue(report['passed']);self.assertFalse(state['hold'])
        self.assertFalse(report['cycle_reexecuted'] or report['cpu_stop_issued'])
        expected=['remove-stopped-client','bind-linux-eth2','linux-eth2-up','release-hold']
        self.assertEqual(report['completed_mutations'],expected);self.assertEqual(report['attempted_mutations'],expected)
        self.assertEqual([x for x in calls if x[0] not in ('baseline','claim')],
            [('rm',r.CLIENT),('bind','2a040000.ethernet'),('ip','link','set','eth1','up'),('rmmod','m7_eth2_power_hold')])
    def test_gate_or_marker_failure_performs_no_mutation(self):
        for kind in ('baseline','proof','marker'):
            with self.subTest(kind=kind):
                report,calls,state=self.workflow(kind)
                self.assertFalse(report['passed']);self.assertEqual(report['attempted_mutations'],[])
                self.assertTrue(state['hold']);self.assertNotIn(('rm',r.CLIENT),calls)
    def test_ambiguous_rm_no_bind_or_retry(self):
        report,calls,state=self.workflow('rm')
        self.assertEqual(report['attempted_mutations'],['remove-stopped-client']);self.assertEqual(report['completed_mutations'],[])
        self.assertEqual(calls.count(('rm',r.CLIENT)),1);self.assertTrue(state['hold'])
    def test_ambiguous_bind_does_not_up_or_release(self):
        report,calls,state=self.workflow('bind')
        self.assertEqual(report['completed_mutations'],['remove-stopped-client']);self.assertTrue(state['hold'])
        self.assertEqual(calls.count(('bind','2a040000.ethernet')),1);self.assertNotIn(('ip','link','set','eth1','up'),calls)
    def test_up_failure_does_not_retry_or_release(self):
        report,calls,state=self.workflow('up')
        self.assertEqual(len(report['attempted_mutations']),3);self.assertTrue(state['hold'])
        self.assertEqual(calls.count(('ip','link','set','eth1','up')),1)
    def test_link_timeout_or_baseline_drift_keeps_hold(self):
        for kind in ('link','drift'):
            with self.subTest(kind=kind):
                report,calls,state=self.workflow(kind);self.assertFalse(report['passed']);self.assertTrue(state['hold'])
                self.assertNotIn(('rmmod','m7_eth2_power_hold'),calls)
    def test_unload_uncertainty_no_retry(self):
        report,calls,state=self.workflow('rmmod')
        self.assertFalse(report['passed']);self.assertTrue(state['hold'])
        self.assertEqual(calls.count(('rmmod','m7_eth2_power_hold')),1)
    def test_permanent_marker_exclusive(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(r,'ROOT',Path(directory)):
            r.claim()
            with self.assertRaises(FileExistsError):r.claim()
            self.assertIn('stopped-only-linux-return',(Path(directory)/'LINUX_RETURN_ATTEMPTED').read_text())
    def test_files_marker_and_original_failure_preserved_gate(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(r,'ROOT',Path(directory)):
            root=Path(directory);(root/'fixed.elf').write_bytes(b'fixed');(root/'ATTEMPTED').write_text('marker')
            (root/'board-result.json').write_bytes(b'failure')
            b=dict(files={'fixed.elf':dict(bytes=5,sha256=hashlib.sha256(b'fixed').hexdigest())},marker='marker',
                original_result_sha256=hashlib.sha256(b'failure').hexdigest(),formal_files={})
            r.check_files(b)
            for key in ('marker','original_result_sha256'):
                with self.assertRaises(RuntimeError):r.check_files(b|{key:'changed'})
            b['files']['fixed.elf']['sha256']='changed'
            with self.assertRaises(RuntimeError):r.check_files(b)
    def test_no_forbidden_actions_in_source(self):
        text=(STAGE/'tests/board/return_powerlink_cycle_p3j_linux.py').read_text()
        for forbidden in ("control('stop'","control('start'","control('create'",'PLK cycle-probe',"command('reboot'",'os.write('):
            self.assertNotIn(forbidden,text)
if __name__=='__main__':unittest.main()
