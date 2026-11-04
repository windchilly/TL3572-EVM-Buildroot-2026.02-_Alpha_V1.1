"""P3j board runner under fake system/transport and synthetic private DRAM only.
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
from test_powerlink_nmt_board import CLIENTS
STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE/'tests/board'))
import powerlink_cycle_p3j_checks as checks
import read_powerlink_cycle_p3j_snapshot as reader
import run_powerlink_cycle_p3j_probe as runner
import run_powerlink_nmt_probe as old
sys.path.pop(0)
IMAGE = STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf'
SYMBOLS = reader.image_symbols(IMAGE)
POOL = SYMBOLS['g_memRegion00'][0]
REPLY = 'PLK UP2 CYCLE ' + ' '.join(k+'='+v for k,v in (checks.PUBLIC | dict(loops='4000',run='2000',drain='20',tx='374')).items())
OWNER = dict(ready='1',pending='0',running='0',seq='1',done='1',cmd='8',rc='0x0',runtime='0x0',
    owner='6',state='0',nmt='0x0',processes='4000',events='16',mode='bounded-cycle-diagnostic')
def evidence(): return dict(owner=OWNER.copy(),result=checks.validate_reply(REPLY))
def fixture():
    raw=bytearray(1504); struct.pack_into('<9I',raw,0,1,0,0,1,1,8,0,0,6)
    struct.pack_into('<5I',raw,40,0,6,0,0,0); struct.pack_into('<2Q',raw,64,4000,16)
    return raw
def cycle_fixture():
    raw=bytearray(608); struct.pack_into('<2I',raw,0,1,608)
    struct.pack_into('<16I',raw,8,0,1,9,0,4000,0,0,0,0,0,374,0,2,0,0,0)
    struct.pack_into('<2Q',raw,72,105,105)
    for offset,state in ((88,1),(128,2),(168,0)):
        struct.pack_into('<5I',raw,offset,state,6,0,0,0)
        struct.pack_into('<2Q',raw,offset+24,4000 if state==0 else 0,16 if state==0 else 0)
    struct.pack_into('<6I',raw,224,0xc003,1,1,0,0,0)
    for offset,counter in ((288,1000),(384,28000000)):
        struct.pack_into('<5Q13I',raw,offset,counter,0,0x500,0,0,4,24000000,2,1,1<<27,0,0,0,0,0xa0,0x80,0,1)
    values=dict(resetSubmitted=1,offSubmitted=1,reached=0x2fd,stopCycleCalls=1,owner=6,pending=0,maxPending=2,
        pendingAtStop=2,txBeforeRun=272,txAtStop=372,runLoops=2000,drainLoops=20,offLoops=1,contextValid=1,watchdogTrips=0,frequency=24000000)
    struct.pack_into('<16I',raw,480,*(values[k] for k in checks.U32_NAMES))
    struct.pack_into('<8Q',raw,544,1000,28010000,25000000,28000000,28000000,10000,1200,0)
    return raw
def heap(phase='COLD', used=40000, peak=50000):
    return checks.validate_heap(dict(g_memTotalSize=1048544, g_memUsage=used, g_memPeakUsage=peak, g_memStartAddr=POOL), POOL, phase)
def abi():
    return dict(passed=True, candidate_sha256=checks.SHA, cache_native=checks.CACHE_LAYOUT.copy(),
        cache_aarch64=checks.CACHE_LAYOUT.copy(), cycle_native=checks.CYCLE_LAYOUT.copy(), cycle_aarch64=checks.CYCLE_LAYOUT.copy(), fsc_native=[32,8], fsc_aarch64=[32,8],
        symbols={name:list(SYMBOLS[name][:2]) for name in checks.PRIVATE_SIZES})
def stopped():
    return checks.validate_snapshot(fixture(),cycle_fixture(),1,1) | {'heap':heap('STOPPED', used=40008, peak=550000),'snapshot_hex':bytes(fixture()).hex(),'cycle_hex':bytes(cycle_fixture()).hex()}

class P3jHeapTests(unittest.TestCase):
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
        config = (STAGE/'tests/board/up-b-m7-plk-cycle-p3j.conf').read_text().splitlines()
        self.assertEqual(config,['[Mica]','Name='+runner.CLIENT,'CPU=5','ClientPath='+str(reader.IMAGE).replace('\\','/'),'AutoBoot=no'])

class P3jReaderTests(unittest.TestCase):
    def memory(self,cold=False):
        raw = bytearray(1504) if cold else fixture()
        if cold: struct.pack_into('<9I',raw,0,1,0,0,0,0,0,0,0,6)
        values = heap()['scalars'] if cold else heap('STOPPED',40008,550000)['scalars']
        data = {SYMBOLS[name][0]:struct.pack('<Q',value) for name,value in values.items()}
        data.update({SYMBOLS['snapshot'][0]:bytes(raw),SYMBOLS['g_ethLease'][0]:bytes(4),
            SYMBOLS['g_excInfoInternal'][0]:bytes(520),SYMBOLS['g_tskCbArray'][0]:struct.pack('<Q',POOL+4096),
            SYMBOLS['g_tskMaxNum'][0]:struct.pack('<I',2),
            SYMBOLS['cycleResult'][0]:bytes(608) if cold else bytes(cycle_fixture()),
            SYMBOLS['cycleReady'][0]:struct.pack('<I',0 if cold else 1),
            SYMBOLS['cycleAttempted'][0]:struct.pack('<I',0 if cold else 1),SYMBOLS['ownerTask'][0]:struct.pack('<I',6)})
        for index,name in enumerate(('rpmsg_tty_task','rpmsg_listen_task','Worker')):
            control = bytearray(80); struct.pack_into('<II',control,16,32768 if name=='Worker' else 4096,6 if name=='Worker' else index+8)
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
        for target in ('snapshot','g_ethLease','cycleReady','cycleAttempted','cycleResult'):
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

class P3jRunnerTests(unittest.TestCase):
    def test_approval_before_board_imports(self):
        with patch.object(sys,'argv',['run','--sha256',checks.SHA]), patch.object(runner.os,'open') as opened, self.assertRaises(RuntimeError): runner.main()
        opened.assert_not_called()
    def test_old_candidate_rejected_before_board_imports(self):
        with patch.object(sys,'argv',['run','--confirm-isolated-p3j-cycle','--sha256',old.SHA]), \
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
        with patch.object(runner,'read_completed',return_value=stopped()), patch.object(runner,'read_stopped',side_effect=lambda image:order.append('DRAM') or stopped()): result=runner.stop_completed(common,IMAGE,evidence(),heap())
        self.assertEqual(order,[('stop',runner.CLIENT),'OFF','DRAM']); self.assertEqual(result['heap_comparison']['used_delta_bytes'],8)
    def test_private_or_heap_failure_never_second_stop(self):
        for failure in (ValueError('private failure'),None):
            common=SimpleNamespace(control=Mock(),confirm_up_cpus_off=Mock())
            report=stopped(); report['heap']['peak_headroom_bytes']=1
            with patch.object(runner,'read_completed',return_value=stopped()), patch.object(runner,'read_stopped',side_effect=failure,return_value=report), self.assertRaises(ValueError):
                runner.stop_completed(common,IMAGE,evidence(),heap())
            common.control.assert_called_once_with('stop',runner.CLIENT)
    def test_stop_command_failure_never_private_read_or_retry(self):
        common=SimpleNamespace(control=Mock(side_effect=RuntimeError('stop failed')),confirm_up_cpus_off=Mock())
        with patch.object(runner,'read_completed',return_value=stopped()), patch.object(runner,'read_stopped') as read, self.assertRaises(RuntimeError): runner.stop_completed(common,IMAGE,evidence(),heap())
        common.control.assert_called_once_with('stop',runner.CLIENT); common.confirm_up_cpus_off.assert_not_called(); read.assert_not_called()
    def workflow(self,scenario):
        # Fake every native/system boundary. Only the local temporary marker,
        # config, ABI and JSON result are real files. NO board is contacted.
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); module=root/'hold.ko'; module.write_bytes(b'fixture')
            (root/(runner.CLIENT+'.conf')).write_text('[Mica]\nName='+runner.CLIENT+'\nCPU=5\nClientPath='+str(root/'tl3572-m7-powerlink-p3j-up-b.elf')+'\nAutoBoot=no\n')
            (root/'p3j-abi.json').write_text(json.dumps(abi()))
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
                if args[0]=='insmod' and scenario=='insmod': raise RuntimeError('ambiguous insmod')
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
                if action=='start' and scenario=='start': raise RuntimeError('ambiguous start')
                if action=='stop' and scenario=='stop': raise RuntimeError('ambiguous stop')
            common=SimpleNamespace(command=command,control=control,confirm_up_cpus_off=Mock(),micad_state=lambda:{'ActiveState':'active'},
                LOG_READER=STAGE/'source/host/up_log_reader.py',
                load_log_reader=lambda:None,log_header=lambda *args:(0,0),new_log_messages=lambda *args:[])
            base=SimpleNamespace(common=common,passive=SimpleNamespace(snapshot=lambda:{},compare_snapshot=Mock()),
                mmu=SimpleNamespace(verify_running=lambda image:{}),fabric=SimpleNamespace(require_fabric_clocks=lambda:0xf000),
                management=lambda: {'drift':1} if scenario=='drift' and ('driver','bind') in calls else {},MODULE=module,MODULE_HASH=hashlib.sha256(b'fixture').hexdigest(),
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
            stack.enter_context(patch.object(sys,'argv',['run','--confirm-isolated-p3j-cycle','--sha256',checks.SHA]))
            stack.enter_context(patch.object(runner,'read_cold_heap',side_effect=ValueError('heap gate') if scenario=='heap' else None,return_value=heap()))
            stack.enter_context(patch.object(runner,'finished',side_effect=RuntimeError('not clean') if scenario=='fault' else None,return_value=evidence()))
            stack.enter_context(patch.object(runner,'read_completed',side_effect=ValueError('bad live') if scenario=='live' else None,return_value=stopped()))
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
        self.assertEqual(calls.count(('diagnostic','PLK cycle-probe')),1)
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
        self.assertLess(calls.index(('stop',runner.CLIENT)),calls.index(('driver','bind')))
    def test_workflow_precommand_heap_failure_retains_without_submission(self):
        result,calls,state=self.workflow('heap')
        self.assertFalse(result['submitted'] or result['cleanup']); self.assertTrue(state['hold'] and state['running'])
        self.assertNotIn(('diagnostic','PLK cycle-probe'),calls); self.assertNotIn(('stop',runner.CLIENT),calls)
    def test_workflow_fault_no_stop_or_rebind(self):
        result,calls,state=self.workflow('fault')
        self.assertTrue(result['submitted']); self.assertFalse(result['cleanup']); self.assertTrue(state['hold'] and state['running'])
        self.assertEqual(calls.count(('diagnostic','PLK cycle-probe')),1)
        self.assertNotIn(('stop',runner.CLIENT),calls); self.assertNotIn(('driver','bind'),calls)
    def test_workflow_ambiguous_ack_only_observes_no_resubmit(self):
        result,calls,_=self.workflow('ambiguous')
        self.assertFalse(result['passed']); self.assertTrue(result['cleanup'])
        self.assertEqual(calls.count(('diagnostic','PLK cycle-probe')),1); self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
    def test_workflow_private_failure_retains_after_one_stop(self):
        result,calls,state=self.workflow('private')
        self.assertFalse(result['cleanup']); self.assertTrue(state['hold']); self.assertFalse(state['running'])
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1); self.assertNotIn(('driver','bind'),calls)
    def test_workflow_live_private_failure_retains_without_stop(self):
        result,calls,state=self.workflow('live')
        self.assertFalse(result['cleanup']); self.assertTrue(state['running'] and state['hold'])
        self.assertNotIn(('stop',runner.CLIENT),calls); self.assertNotIn(('driver','bind'),calls)
    def test_workflow_ambiguous_insmod_or_start_retains(self):
        for scenario in ('insmod','start'):
            result,calls,state=self.workflow(scenario)
            self.assertFalse(result['submitted'] or result['cleanup'])
            self.assertNotIn(('stop',runner.CLIENT),calls); self.assertNotIn(('driver','bind'),calls)
            self.assertNotIn(('rmmod','m7_eth2_power_hold'),calls)
    def test_workflow_stop_failure_never_second_stop_or_rebind(self):
        result,calls,state=self.workflow('stop')
        self.assertFalse(result['cleanup']); self.assertTrue(state['hold'])
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1); self.assertNotIn(('driver','bind'),calls)
    def test_workflow_restore_drift_keeps_hold_and_no_second_stop(self):
        result,calls,state=self.workflow('drift')
        self.assertFalse(result['cleanup']); self.assertTrue(state['hold'])
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
        self.assertNotIn(('rmmod','m7_eth2_power_hold'),calls)
    def test_runner_scope_and_order_source(self):
        text=(STAGE/'tests/board/run_powerlink_cycle_p3j_probe.py').read_text()
        self.assertEqual(text.count("diagnostic(fd, 'PLK cycle-probe')"),1)
        self.assertLess(text.index('before_heap = read_cold_heap'),text.index('submitted = True'))
        self.assertLess(text.index('stopped = stop_completed'),text.index("common.control('rm', CLIENT)"))
        for forbidden in ('g.ROOT =','g.SHA =',"command('reboot'",'M7 run','sendto('): self.assertNotIn(forbidden,text)
class P3jCycleChecksTests(unittest.TestCase):
    def test_valid_full_cycle_and_replies(self):
        report=checks.validate_snapshot(fixture(),cycle_fixture(),1,1)
        checks.match_replies(report,OWNER,checks.validate_reply(REPLY))
        self.assertEqual(report['cycle']['reached'],0x2fd)
    def test_header_size_version_and_publish_required(self):
        for size in (0,472,496,607,609):
            with self.assertRaises(ValueError): checks.decode_cycle(bytes(size))
        for offset,value in ((0,0),(0,2),(4,1504)):
            raw=cycle_fixture();struct.pack_into('<I',raw,offset,value)
            with self.assertRaises(ValueError): checks.validate_snapshot(fixture(),raw,1,1)
        for flags in ((0,0),(0,1),(1,0),(2,1)):
            with self.assertRaises(ValueError): checks.validate_snapshot(fixture(),cycle_fixture(),*flags)
    def test_every_owner_mailbox_gate(self):
        for offset in (0,4,8,12,16,20,24,28,32,80,576):
            raw=fixture();raw[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError): checks.validate_snapshot(raw,cycle_fixture(),1,1)
    def test_cycle_policy_u32_failures(self):
        bad=dict(resetSubmitted=0,offSubmitted=0,reached=0x21c,stopCycleCalls=2,owner=7,pending=1,maxPending=8,
            pendingAtStop=0,txBeforeRun=372,txAtStop=375,runLoops=0,drainLoops=0,offLoops=33,
            contextValid=0,watchdogTrips=1,frequency=25000000)
        for name,value in bad.items():
            raw=cycle_fixture();struct.pack_into('<I',raw,480+checks.U32_NAMES.index(name)*4,value)
            with self.subTest(name=name),self.assertRaises(ValueError): checks.validate_snapshot(fixture(),raw,1,1)
    def test_timer_and_counter_budgets(self):
        bad=dict(endCounter=200000000,runCounter=28010001,lastTxCounter=0,pendingCounter=0,
            maxGapTicks=28010001,maxLateTicks=12001,skippedPeriods=1)
        for name,value in bad.items():
            raw=cycle_fixture();struct.pack_into('<Q',raw,544+checks.U64_NAMES.index(name)*8,value)
            with self.subTest(name=name),self.assertRaises(ValueError): checks.validate_snapshot(fixture(),raw,1,1)
    def test_lifecycle_failure_traffic_lease_or_incomplete(self):
        for offset in (0,4,8,12,16,20,24,28,32,36,44,52,56,60):
            raw=cycle_fixture();raw[8+offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError): checks.validate_snapshot(fixture(),raw,1,1)
    def test_actual_hardware_stop_and_timer_preservation(self):
        for offset,mask in ((264,1),(268,1),(272,1),(276,1),(280,1),(284,1),
                (424,1),(428,1),(432,1),(440,1<<30),(452,1<<30),(456,1<<29),(460,1),(464,1)):
            raw=cycle_fixture();value=struct.unpack_from('<I',raw,offset)[0];struct.pack_into('<I',raw,offset,value^mask)
            with self.subTest(offset=offset),self.assertRaises(ValueError): checks.validate_snapshot(fixture(),raw,1,1)
    def test_reply_wrong_profile_failure_or_missing(self):
        for text in (REPLY.replace('CYCLE','NMT'),REPLY.replace('stage=9','stage=6'),REPLY.replace('clean=1','clean=0'),
                REPLY.replace('tx=374','tx=0'),REPLY+' extra=0',REPLY.replace('loops=4000','loops=4000000')):
            with self.subTest(text=text),self.assertRaises(ValueError): checks.validate_reply(text)
    def test_cross_reply_mismatch(self):
        report=stopped()
        for key,value in (('tx','375'),('run','1999'),('drain','21'),('loops','4001')):
            with self.assertRaises(ValueError): checks.match_replies(report,OWNER,checks.validate_reply(REPLY)|{key:value})
    def test_full_live_private_failure_prevents_first_stop(self):
        common=SimpleNamespace(control=Mock(),confirm_up_cpus_off=Mock())
        with patch.object(runner,'read_completed',side_effect=ValueError('pending/nonquiet')), self.assertRaises(ValueError):
            runner.stop_completed(common,IMAGE,evidence(),heap())
        common.control.assert_not_called()
    def test_private_changed_across_off_retains_after_one_stop(self):
        common=SimpleNamespace(control=Mock(),confirm_up_cpus_off=Mock())
        with patch.object(runner,'read_completed',return_value=stopped()), \
                patch.object(runner,'read_stopped',return_value=stopped()|{'cycle_hex':'changed'}), self.assertRaises(ValueError):
            runner.stop_completed(common,IMAGE,evidence(),heap())
        common.control.assert_called_once_with('stop',runner.CLIENT)
    def test_transport_whitelist_and_short_write_no_retry(self):
        for command in ('PLK nmt-probe','PLK start','M7 run can','PLK reset'):
            with patch.object(runner.os,'write') as write, self.assertRaises(ValueError): runner.diagnostic(4,command)
            write.assert_not_called()
        with patch.object(runner.os,'write',return_value=1) as write,self.assertRaises(RuntimeError): runner.diagnostic(4,'PLK cycle-probe')
        write.assert_called_once()
    def test_observation_only_completion(self):
        state='PLK UP2 '+' '.join(k+'='+v for k,v in OWNER.items())
        with patch.object(runner,'diagnostic',side_effect=[state,REPLY,runner.IDLE]) as command,redirect_stdout(io.StringIO()):
            self.assertEqual(runner.finished(4),evidence())
        self.assertEqual([c.args[1] for c in command.call_args_list],['PLK status','PLK cycle-status','M7 status'])
    def test_incomplete_observation_never_submits_or_stops(self):
        with patch.object(runner.time,'monotonic',side_effect=[0,1,21]),patch.object(runner.time,'sleep'), \
                patch.object(runner,'diagnostic',return_value='PLK UP2 done=0 pending=0 running=1') as command, self.assertRaises(RuntimeError):
            runner.finished(4)
        command.assert_called_once_with(4,'PLK status')
    def test_bad_completed_observation_does_not_report_success(self):
        state='PLK UP2 '+' '.join(k+'='+v for k,v in OWNER.items())
        with patch.object(runner.time,'monotonic',side_effect=[0,1,21]),patch.object(runner.time,'sleep'), \
                patch.object(runner,'diagnostic',side_effect=[state,REPLY.replace('trips=0','trips=1')]) as command, \
                redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError): runner.finished(4)
        self.assertEqual([c.args[1] for c in command.call_args_list],['PLK status','PLK cycle-status'])
    def test_actual_native_capture_and_abi_proof(self):
        archive=STAGE/'tests/powerlink-cycle-p3j-runner-20261104'
        checks.validate_abi_report(json.loads((archive/'p3j-abi.json').read_text()),SYMBOLS)
        for name in ('normal-host.bin','heap-full-host.bin'):
            raw=(archive/name).read_bytes();life=checks.decode_cycle(raw)['lifecycle']
            mailbox=bytearray(1504);struct.pack_into('<9I',mailbox,0,1,0,0,1,1,8,0,0,life['final']['owner'])
            mailbox[40:80]=raw[168:208]
            report=checks.validate_snapshot(mailbox,raw,1,1)
            self.assertEqual(report['lifecycle']['tx'],374)
            self.assertEqual(report['lifecycle']['loops'],32142)
if __name__ == '__main__': unittest.main()
