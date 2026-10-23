"""P3h board runner under fake system/transport and synthetic private DRAM only.
No board access. Real local pinned ELF is used for symbol/range validation.
"""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_powerlink_nmt_board import fixture, evidence, CLIENTS, OWNER, REPLY
STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE/'tests/board'))
import powerlink_nmt_p3h_checks as checks
import read_powerlink_nmt_p3h_snapshot as reader
import run_powerlink_nmt_p3h_probe as runner
import run_powerlink_nmt_probe as old
sys.path.pop(0)
IMAGE = STAGE/'tests/powerlink-nmt-p3h-20261023/candidates/tl3572-m7-powerlink-p3h-up-b.elf'
SYMBOLS = reader.image_symbols(IMAGE)
POOL = SYMBOLS['g_memRegion00'][0]
def heap(phase='COLD', used=40000, peak=50000):
    return checks.validate_heap(dict(g_memTotalSize=1048544, g_memUsage=used, g_memPeakUsage=peak, g_memStartAddr=POOL), POOL, phase)
def abi():
    return dict(passed=True, candidate_sha256=checks.SHA, cache_native=checks.CACHE_LAYOUT.copy(),
        cache_aarch64=checks.CACHE_LAYOUT.copy(), fsc_native=[32,8], fsc_aarch64=[32,8],
        symbols={name:list(SYMBOLS[name][:2]) for name in checks.PRIVATE_SIZES})
def stopped():
    return checks.validate_snapshot(fixture()) | {'heap':heap('STOPPED', used=40008, peak=550000)}

class P3hHeapTests(unittest.TestCase):
    def test_heap_full_and_usage_delta_not_leak_verdict(self):
        result = checks.match_heap(heap(), heap('STOPPED',40008,550000))
        self.assertEqual(result['used_delta_bytes'],8)
        self.assertEqual(result['peak_headroom_bytes'],498544)
    def test_heap_bad_total_start_or_counters(self):
        base = heap()['scalars']
        for key, value in dict(g_memTotalSize=524256,g_memUsage=60000,g_memPeakUsage=1048545,g_memStartAddr=POOL+8).items():
            with self.subTest(key=key), self.assertRaises(ValueError): checks.validate_heap(base | {key:value},POOL,'COLD')
    def test_heap_types_phase_or_missing_fields(self):
        for values,pool,phase in (({},POOL,'COLD'),(heap()['scalars'],POOL,'LIVE'),
                (heap()['scalars']|{'g_memUsage':-1},POOL,'COLD'),(heap()['scalars'],0,'COLD')):
            with self.assertRaises(ValueError): checks.validate_heap(values,pool,phase)
    def test_initial_allowance_and_peak_margin(self):
        with self.assertRaises(ValueError): heap(used=300000,peak=300000)
        with self.assertRaises(ValueError): heap('STOPPED',40000,800000)
        good = heap('COLD',1048544-checks.MIN_INITIAL_FREE,1048544-checks.MIN_INITIAL_FREE)
        self.assertEqual(good['free_bytes'],checks.MIN_INITIAL_FREE)
    def test_heap_pair_cannot_forge_report_or_regress_peak(self):
        for after in (heap('STOPPED')|{'candidate_sha256':old.SHA},heap('STOPPED',40000,49000)):
            with self.assertRaises(ValueError): checks.match_heap(heap(),after)
    def test_abi_proof_exact_image_layout_symbols(self):
        checks.validate_abi_report(abi(),SYMBOLS)
        for key,value in [('candidate_sha256',old.SHA),('passed',1),('cache_aarch64',[1008]),('fsc_aarch64',[16,8]),('symbols',{})]:
            with self.subTest(key=key), self.assertRaises(ValueError): checks.validate_abi_report(abi()|{key:value},SYMBOLS)
    def test_wrong_elf_identity_before_private_io(self):
        memory = SimpleNamespace(read_reserved_dram=Mock())
        with patch.dict(sys.modules,{'integrated_mmu_resources':memory}), self.assertRaises(RuntimeError):
            reader.image_symbols(STAGE/'tests/powerlink-nmt-p3g-20261023/candidates/tl3572-m7-powerlink-p3g-up-b.elf')
        memory.read_reserved_dram.assert_not_called()
    def test_old_profile_unchanged_and_new_conf_separate(self):
        self.assertEqual(old.SHA,'85e78eb4bb150633e695014b5ecc55401a048a2707175a031b97a2e00567f68e')
        self.assertNotEqual(runner.ROOT,old.ROOT); self.assertNotEqual(runner.CLIENT,old.CLIENT)
        config = (STAGE/'tests/board/up-b-m7-plk-nmt-p3h.conf').read_text().splitlines()
        self.assertEqual(config,['[Mica]','Name='+runner.CLIENT,'CPU=5','ClientPath='+str(reader.IMAGE).replace('\\','/'),'AutoBoot=no'])

class P3hReaderTests(unittest.TestCase):
    def memory(self,cold=False):
        raw = bytearray(1504) if cold else fixture()
        if cold: struct.pack_into('<9I',raw,0,1,0,0,0,0,0,0,0,6)
        values = heap()['scalars'] if cold else heap('STOPPED',40008,550000)['scalars']
        data = {SYMBOLS[name][0]:struct.pack('<Q',value) for name,value in values.items()}
        data.update({SYMBOLS['snapshot'][0]:bytes(raw),SYMBOLS['g_ethLease'][0]:bytes(4),
            SYMBOLS['g_excInfoInternal'][0]:bytes(520),SYMBOLS['g_tskCbArray'][0]:struct.pack('<Q',POOL+4096),
            SYMBOLS['g_tskMaxNum'][0]:struct.pack('<I',1)})
        for index,name in enumerate(('rpmsg_tty_task','rpmsg_listen_task')):
            control = bytearray(80); struct.pack_into('<II',control,16,4096,index+8)
            struct.pack_into('<Q',control,48,SYMBOLS[name][0]); data[POOL+4096+index*800]=bytes(control)
        order=[]
        def read(address,size):
            order.append((address,size)); self.assertTrue(0x7c200000 <= address <= 0x7ca00000-size)
            self.assertLessEqual(size,1504); self.assertEqual(len(data[address]),size); return data[address]
        common = SimpleNamespace(confirm_up_cpus_off=Mock(side_effect=lambda:order.append('OFF')))
        return data,order,common,SimpleNamespace(read_reserved_dram=Mock(side_effect=read))
    def test_cold_heap_live_not_stop_proof(self):
        _,order,common,memory = self.memory(cold=True)
        with patch.dict(sys.modules,{'integrated_mmu_resources':memory,'run_can_direct_pair':common}):
            self.assertEqual(reader.read_cold_heap(IMAGE),heap())
        common.confirm_up_cpus_off.assert_not_called(); self.assertNotIn('OFF',order)
    def test_cold_rejects_any_prior_command_or_lease(self):
        for target in ('snapshot','g_ethLease'):
            data,_,common,memory = self.memory(cold=True); raw=bytearray(data[SYMBOLS[target][0]])
            raw[20 if target=='snapshot' else 0]=1; data[SYMBOLS[target][0]]=bytes(raw)
            with patch.dict(sys.modules,{'integrated_mmu_resources':memory,'run_can_direct_pair':common}), self.assertRaises(RuntimeError):
                reader.read_cold_heap(IMAGE)
    def test_cold_exception_rejected(self):
        data,_,_,memory = self.memory(cold=True); raw=bytearray(520); struct.pack_into('<I',raw,112,7)
        data[SYMBOLS['g_excInfoInternal'][0]]=bytes(raw)
        with patch.dict(sys.modules,{'integrated_mmu_resources':memory}), self.assertRaises(RuntimeError): reader.read_cold_heap(IMAGE)
    def test_stopped_off_before_and_after_metadata_only(self):
        _,order,common,memory = self.memory()
        with patch.dict(sys.modules,{'integrated_mmu_resources':memory,'run_can_direct_pair':common}): report=reader.read_stopped(IMAGE)
        self.assertEqual(order[0],'OFF'); self.assertEqual(order[-1],'OFF')
        self.assertEqual(report['heap'],heap('STOPPED',40008,550000)); self.assertEqual(report['candidate_sha256'],checks.SHA)
    def test_stopped_exception_or_actual_stack_mismatch(self):
        for target in ('exception','stack'):
            data,_,common,memory = self.memory(); address=SYMBOLS['g_excInfoInternal'][0] if target=='exception' else POOL+4096
            raw=bytearray(data[address]); struct.pack_into('<I',raw,112 if target=='exception' else 16,7 if target=='exception' else 8192); data[address]=bytes(raw)
            with patch.dict(sys.modules,{'integrated_mmu_resources':memory,'run_can_direct_pair':common}), self.assertRaises(RuntimeError): reader.read_stopped(IMAGE)
    def test_cpu_not_off_never_reads_dram(self):
        _,_,common,memory=self.memory(); common.confirm_up_cpus_off.side_effect=RuntimeError('CPU live')
        with patch.dict(sys.modules,{'integrated_mmu_resources':memory,'run_can_direct_pair':common}), self.assertRaises(RuntimeError): reader.read_stopped(IMAGE)
        memory.read_reserved_dram.assert_not_called()
    def test_unstable_heap_rejected(self):
        data,_,_,memory=self.memory(cold=True); address=SYMBOLS['g_memUsage'][0]; calls=0; normal=memory.read_reserved_dram.side_effect
        def changing(addr,size):
            nonlocal calls
            if addr==address:
                calls+=1
                if calls==2: data[address]=struct.pack('<Q',40001)
            return normal(addr,size)
        memory.read_reserved_dram.side_effect=changing
        with patch.dict(sys.modules,{'integrated_mmu_resources':memory}), self.assertRaises(RuntimeError): reader.read_cold_heap(IMAGE)

class P3hRunnerTests(unittest.TestCase):
    def test_approval_before_board_imports(self):
        with patch.object(sys,'argv',['run','--sha256',checks.SHA]), patch.object(runner.os,'open') as opened, self.assertRaises(RuntimeError): runner.main()
        opened.assert_not_called()
    def test_old_candidate_rejected_before_board_imports(self):
        with patch.object(sys,'argv',['run','--confirm-isolated-p3h-nmt-reset','--sha256',old.SHA]), \
             patch.object(runner.os,'geteuid',return_value=0,create=True), patch.object(runner.os,'open') as opened, self.assertRaises(RuntimeError): runner.main()
        opened.assert_not_called()
    def test_marker_exclusive_and_new_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); runner.claim_attempt(root,'boot')
            with self.assertRaises(FileExistsError): runner.claim_attempt(root,'boot')
            self.assertIn(checks.SHA,(root/'ATTEMPTED').read_text())
    def test_no_stop_before_heap_and_completion_proof(self):
        common=SimpleNamespace(control=Mock(),confirm_up_cpus_off=Mock())
        for result,before in ((None,heap()),(evidence(),heap()|{'candidate_sha256':old.SHA})):
            with self.assertRaises((ValueError,RuntimeError)): runner.stop_completed(common,IMAGE,result,before)
        common.control.assert_not_called()
    def test_stop_once_then_off_private_and_heap_match(self):
        order=[]; common=SimpleNamespace(control=lambda *args:order.append(args),confirm_up_cpus_off=lambda:order.append('OFF'))
        with patch.object(runner,'read_stopped',side_effect=lambda image:order.append('DRAM') or stopped()): result=runner.stop_completed(common,IMAGE,evidence(),heap())
        self.assertEqual(order,[('stop',runner.CLIENT),'OFF','DRAM']); self.assertEqual(result['heap_comparison']['used_delta_bytes'],8)
    def test_private_or_heap_failure_never_second_stop(self):
        for failure in (ValueError('private failure'),None):
            common=SimpleNamespace(control=Mock(),confirm_up_cpus_off=Mock())
            report=stopped(); report['heap']['peak_headroom_bytes']=1
            with patch.object(runner,'read_stopped',side_effect=failure,return_value=report), self.assertRaises(ValueError):
                runner.stop_completed(common,IMAGE,evidence(),heap())
            common.control.assert_called_once_with('stop',runner.CLIENT)
    def test_stop_command_failure_never_private_read_or_retry(self):
        common=SimpleNamespace(control=Mock(side_effect=RuntimeError('stop failed')),confirm_up_cpus_off=Mock())
        with patch.object(runner,'read_stopped') as read, self.assertRaises(RuntimeError): runner.stop_completed(common,IMAGE,evidence(),heap())
        common.control.assert_called_once_with('stop',runner.CLIENT); common.confirm_up_cpus_off.assert_not_called(); read.assert_not_called()
    def workflow(self,scenario):
        # Fake every native/system boundary. Only the local temporary marker,
        # config, ABI and JSON result are real files. NO board is contacted.
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); module=root/'hold.ko'; module.write_bytes(b'fixture')
            (root/(runner.CLIENT+'.conf')).write_text('[Mica]\nName='+runner.CLIENT+'\nCPU=5\nClientPath='+str(root/'tl3572-m7-powerlink-p3h-up-b.elf')+'\nAutoBoot=no\n')
            (root/'p3h-abi.json').write_text(json.dumps(abi()))
            state=dict(hold=False,driver=True,created=False,running=False); calls=[]
            class FakePath:
                def __init__(self,value): self.value=value
                @property
                def name(self): return self.value.rsplit('/',1)[-1]
                def __truediv__(self,name): return FakePath(self.value+'/'+name)
                def exists(self):
                    if self.value.endswith('/driver'): return state['driver']
                    if self.value=='/sys/module/m7_eth2_power_hold': return state['hold']
                    return False
                def glob(self,pattern): return ['/dev/ttyRPMSG0'] if state['running'] else []
                def read_text(self):
                    if self.value.endswith('boot_id'): return 'test-boot\n'
                    if self.value.endswith('tainted'): return '4096'
                    return 'nvm0 on fixture\n m7-eth2-power-hold\n'
                def write_text(self,text):
                    calls.append(('driver',self.name)); state['driver']=self.name=='bind'
            def command(*args):
                calls.append(args)
                if args[0]=='uname': return '6.12.69-gf1b67c293213'
                if args[:2]==('mcsctl','status'): return CLIENTS
                if args[0]=='insmod': state['hold']=True
                if args[0]=='rmmod': state['hold']=False
                return ''
            def control(action,*args):
                calls.append((action,*args))
                if action=='create': state['created']=True
                elif action=='start': state['running']=True
                elif action=='stop': state['running']=False
                elif action=='rm': state['created']=False
            common=SimpleNamespace(command=command,control=control,confirm_up_cpus_off=Mock(),micad_state=lambda:{'ActiveState':'active'},
                load_log_reader=lambda:None,log_header=lambda *args:(0,0),new_log_messages=lambda *args:[])
            base=SimpleNamespace(common=common,passive=SimpleNamespace(snapshot=lambda:{},compare_snapshot=Mock()),
                mmu=SimpleNamespace(verify_running=lambda image:{}),fabric=SimpleNamespace(require_fabric_clocks=lambda:0xf000),
                management=lambda:{},MODULE=module,MODULE_HASH=hashlib.sha256(b'fixture').hexdigest(),
                DRIVER=FakePath('/driver'),DEVICE=FakePath('/device'))
            def diagnostic(fd,text):
                calls.append(('diagnostic',text))
                if text=='M7 status': return runner.IDLE
                if text=='PLK status': return 'PLK UP2 '+ ' '.join(k+'='+v for k,v in
                    (OWNER|dict(seq='0',done='0',cmd='0',state='0',processes='0',events='0')).items())
                if scenario=='ambiguous': raise RuntimeError('ambiguous acceptance')
                return 'PLK UP2 ACCEPTED seq=1'
            stack.enter_context(patch.dict(sys.modules,{'run_powerlink_eth_probe':base,'termios':SimpleNamespace(TCIOFLUSH=2,tcflush=Mock()),'tty':SimpleNamespace(setraw=Mock())}))
            for name,value in dict(ROOT=root,Path=FakePath,linux_full=lambda base:(SimpleNamespace(name='eth1'),None),
                image_symbols=lambda image:SYMBOLS,diagnostic=diagnostic).items(): stack.enter_context(patch.object(runner,name,value))
            stack.enter_context(patch.object(runner.os,'geteuid',return_value=0,create=True))
            # Windows lacks these POSIX flags. Supply fixture-only values;
            # the actual os.open/close and terminal APIs are mocked below.
            for name,value in (('O_NONBLOCK',0x10000),('O_NOCTTY',0x20000)):
                stack.enter_context(patch.object(runner.os,name,value,create=True))
            stack.enter_context(patch.object(runner.os,'open',return_value=123)); stack.enter_context(patch.object(runner.os,'close'))
            stack.enter_context(patch.object(sys,'argv',['run','--confirm-isolated-p3h-nmt-reset','--sha256',checks.SHA]))
            stack.enter_context(patch.object(runner,'read_cold_heap',side_effect=ValueError('heap gate') if scenario=='heap' else None,return_value=heap()))
            stack.enter_context(patch.object(runner,'finished',side_effect=RuntimeError('not clean') if scenario=='fault' else None,return_value=evidence()))
            stack.enter_context(patch.object(runner,'read_stopped',side_effect=ValueError('bad private') if scenario=='private' else None,return_value=stopped()))
            with redirect_stdout(io.StringIO()):
                if scenario=='normal': runner.main()
                else:
                    with self.assertRaises(RuntimeError): runner.main()
            result=json.loads((root/'board-result.json').read_text())
            return result,calls,state
    def test_workflow_success_complete_stop_restore(self):
        result,calls,state=self.workflow('normal')
        self.assertTrue(result['passed'] and result['cleanup']); self.assertFalse(state['hold'] or state['running'] or state['created'])
        self.assertEqual(calls.count(('diagnostic','PLK nmt-probe')),1)
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
        self.assertLess(calls.index(('stop',runner.CLIENT)),calls.index(('driver','bind')))
    def test_workflow_precommand_heap_failure_retains_without_submission(self):
        result,calls,state=self.workflow('heap')
        self.assertFalse(result['submitted'] or result['cleanup']); self.assertTrue(state['hold'] and state['running'])
        self.assertNotIn(('diagnostic','PLK nmt-probe'),calls); self.assertNotIn(('stop',runner.CLIENT),calls)
    def test_workflow_fault_no_stop_or_rebind(self):
        result,calls,state=self.workflow('fault')
        self.assertTrue(result['submitted']); self.assertFalse(result['cleanup']); self.assertTrue(state['hold'] and state['running'])
        self.assertEqual(calls.count(('diagnostic','PLK nmt-probe')),1)
        self.assertNotIn(('stop',runner.CLIENT),calls); self.assertNotIn(('driver','bind'),calls)
    def test_workflow_ambiguous_ack_only_observes_no_resubmit(self):
        result,calls,_=self.workflow('ambiguous')
        self.assertFalse(result['passed']); self.assertTrue(result['cleanup'])
        self.assertEqual(calls.count(('diagnostic','PLK nmt-probe')),1); self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
    def test_workflow_private_failure_retains_after_one_stop(self):
        result,calls,state=self.workflow('private')
        self.assertFalse(result['cleanup']); self.assertTrue(state['hold']); self.assertFalse(state['running'])
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1); self.assertNotIn(('driver','bind'),calls)
    def test_runner_scope_and_order_source(self):
        text=(STAGE/'tests/board/run_powerlink_nmt_p3h_probe.py').read_text()
        self.assertEqual(text.count("diagnostic(fd, 'PLK nmt-probe')"),1)
        self.assertLess(text.index('before_heap = read_cold_heap'),text.index('submitted = True'))
        self.assertLess(text.index('stopped = stop_completed'),text.index("common.control('rm', CLIENT)"))
        for forbidden in ('g.ROOT =','g.SHA =',"command('reboot'",'M7 run','sendto('): self.assertNotIn(forbidden,text)
if __name__ == '__main__': unittest.main()
