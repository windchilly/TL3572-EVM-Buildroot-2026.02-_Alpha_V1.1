"""P3j runner-v2 software simulation using actual recorded private TCB bytes.
All native/system/transport boundaries fake; no board or packet IO.
"""
from contextlib import ExitStack,redirect_stdout
import ast
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from test_powerlink_cycle_p3j_tcb import fixture as actual_fixture,IMAGE
from test_powerlink_nmt_board import CLIENTS
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
import read_powerlink_cycle_p3j_v2_snapshot as reader
import run_powerlink_cycle_p3j_v2_probe as runner
import run_powerlink_cycle_p3j_probe as historical
sys.path.pop(0)
OLD=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
PREPARED=STAGE/'tests/powerlink-cycle-p3j-runner-20261104'
def cache_abi():return json.loads((PREPARED/'p3j-abi.json').read_text())
def tcb_abi():return json.loads((OLD/'tcb-abi.json').read_text())
def evidence():return json.loads((OLD/'board-result.json').read_text())['completion']
def cold():return json.loads((OLD/'board-result.json').read_text())['heap_before']
def private_fixture(kind='normal'):
    report,records,symbols=actual_fixture()
    values=dict(snapshot=bytes.fromhex(report['snapshot_hex']),cycleResult=bytes.fromhex(report['cycle_hex']),
        cycleReady=struct.pack('<I',1),cycleAttempted=struct.pack('<I',1),g_ethLease=bytes(4),g_excInfoInternal=bytes(520),
        ownerTask=struct.pack('<I',6),g_tskCbArray=struct.pack('<Q',report['tcb_pointer']),g_tskMaxNum=struct.pack('<I',report['tcb_maximum']))
    values.update({k:struct.pack('<Q',v) for k,v in report['heap']['scalars'].items()})
    if kind=='tcb':struct.pack_into('<Q',records[6],32,0)
    if kind=='wrapper':struct.pack_into('<Q',records[8],32,0)
    if kind=='lease':values['g_ethLease']=struct.pack('<I',2)
    if kind=='bounds':values['g_tskMaxNum']=struct.pack('<I',64)
    if kind=='publish':values['cycleReady']=bytes(4)
    if kind=='heap':values['g_memPeakUsage']=struct.pack('<Q',800000)
    if kind=='exception':
        raw=bytearray(520);struct.pack_into('<I',raw,112,7);values['g_excInfoInternal']=bytes(raw)
    def private(name):return values[name]
    def memory(address,size):
        if size!=80 or not 0x7c200000<=address<=0x7ca00000-size:raise AssertionError('not bounded private TCB prefix')
        return bytes(records[(address-report['tcb_pointer'])//800])
    return report,records,symbols,private,memory

class V2ReaderTests(unittest.TestCase):
    def test_exact_22_prepared_inputs_and_flat_import_closure(self):
        from make_powerlink_cycle_p3j_v2_runtime_inputs import runtime_inputs,REPO
        runtime=json.loads((STAGE/'tests/powerlink-cycle-p3j-v2-20261104/runtime-inputs.json').read_text())
        paths=runtime_inputs();self.assertIs(runtime['prepared_only'],True)
        self.assertEqual(set(runtime['files']),set(paths));self.assertEqual(len(paths),22)
        for name,value in paths.items():
            recorded=runtime['files'][name]
            self.assertEqual((recorded['bytes'],recorded['sha256']),(value['bytes'],value['sha256']))
            relative=(REPO/value['path']).relative_to(STAGE).as_posix()
            self.assertEqual(recorded['path'],'stages/stage07-peripheral-partition/'+relative)
        self.assertEqual(runtime['board_root'],str(runner.ROOT).replace('\\','/'))
        self.assertEqual(runtime['client'],runner.CLIENT)
        for name,value in paths.items():
            if not name.endswith('.py'):continue
            tree=ast.parse((REPO/value['path']).read_text(encoding='utf-8'))
            imported=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imported += [x.name.split('.')[0] for x in node.names]
                elif isinstance(node,ast.ImportFrom) and node.module:imported.append(node.module.split('.')[0])
            for module in imported:
                if any((folder/(module+'.py')).is_file() for folder in (STAGE/'tests/board',STAGE/'tests')):
                    self.assertIn(module+'.py',paths,'missing flat runtime import from '+name)
    def test_old_runtime_does_not_get_rewritten(self):
        runtime=json.loads((PREPARED/'runtime-inputs.json').read_text())
        self.assertEqual(len(runtime['files']),19)
        self.assertEqual(runtime['board_root'],str(historical.ROOT).replace('\\','/'))
        self.assertNotIn('run_powerlink_cycle_p3j_v2_probe.py',runtime['files'])
    def test_actual_tcb_compiler_proof_required(self):
        reader.validate_tcb_abi(tcb_abi(),cache_abi())
        for key,value in (('passed',1),('candidate_sha256','old'),('native',[800,16,20,24,48,32]),
                ('aarch64',[]),('fields',[]),('source_sha256',{})):
            with self.subTest(key=key),self.assertRaises(ValueError):reader.validate_tcb_abi(tcb_abi()|{key:value},cache_abi())
        with self.assertRaises(ValueError):reader.validate_tcb_abi(tcb_abi(),cache_abi()|{'rtos_archive_sha256':'other-library'})
    def read(self,kind='normal'):
        report,records,symbols,private,memory=private_fixture(kind);order=[]
        common=SimpleNamespace(confirm_up_cpus_off=Mock(side_effect=lambda:order.append('OFF')))
        def read(address,size):order.append('TCB');return memory(address,size)
        if kind=='live':common.confirm_up_cpus_off.side_effect=RuntimeError('CPU live')
        with patch.object(reader,'image_symbols',return_value=symbols),patch.object(reader.shared,'private_reader',return_value=private), \
                patch.dict(sys.modules,{'run_can_direct_pair':common,'integrated_mmu_resources':SimpleNamespace(read_reserved_dram=read)}):
            if kind=='normal':result=reader.read_stopped(IMAGE)
            else:
                with self.assertRaises((RuntimeError,ValueError)):reader.read_stopped(IMAGE)
                result=None
        return result,order
    def test_actual_records_pass_with_off_before_after(self):
        report,order=self.read();self.assertEqual(order[0],'OFF');self.assertEqual(order[-1],'OFF')
        self.assertEqual(len(report['tcb_prefix_hex']),17)
        self.assertEqual(sorted((x['name'],x['allocated_stack']) for x in report['threads']),
            [('PLKowner',32768),('rpmsg_listen_task',4096),('rpmsg_tty_task',4096)])
        self.assertEqual(report['lifecycle']['tx'],376);self.assertEqual(report['heap']['peak_headroom_bytes'],504896)
    def test_live_cpu_no_metadata_read(self):
        _,order=self.read('live');self.assertEqual(order,[])
    def test_private_failures_keep_rejecting(self):
        for kind in ('tcb','wrapper','lease','bounds','publish','heap','exception'):
            with self.subTest(kind=kind):self.read(kind)
    def test_live_helpers_use_v2_image_not_old_default(self):
        for name in ('read_cold_heap','read_completed'):
            with patch.object(reader.shared,name,return_value={}) as method:getattr(reader,name)()
            method.assert_called_once_with(reader.IMAGE)
        self.assertNotEqual(reader.IMAGE,reader.shared.IMAGE)
    def test_profiles_and_old_files_are_separate(self):
        self.assertNotEqual(runner.ROOT,historical.ROOT);self.assertNotEqual(runner.CLIENT,historical.CLIENT)
        config=(STAGE/'tests/board/up-b-m7-plk-cycle-p3j-v2.conf').read_text().splitlines()
        self.assertEqual(config,['[Mica]','Name='+runner.CLIENT,'CPU=5','ClientPath='+str(reader.IMAGE).replace('\\','/'),'AutoBoot=no'])

class V2WorkflowTests(unittest.TestCase):
    def workflow(self,kind='normal'):
        report,records,symbols,private,memory=private_fixture(kind)
        calls=[];state=dict(hold=False,driver=True,created=False,running=False)
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);module=root/'hold.ko';module.write_bytes(b'fixture')
            image=root/'tl3572-m7-powerlink-p3j-up-b.elf'
            (root/(runner.CLIENT+'.conf')).write_text('[Mica]\nName='+runner.CLIENT+'\nCPU=5\nClientPath='+str(image)+'\nAutoBoot=no\n')
            (root/'p3j-abi.json').write_text(json.dumps(cache_abi()))
            (root/'tcb-abi.json').write_text(json.dumps(tcb_abi()|({'aarch64':[]} if kind=='abi' else {})))
            class FakePath:
                def __init__(self,value):self.value=value
                @property
                def name(self):return self.value.rsplit('/',1)[-1]
                def __truediv__(self,name):return FakePath(self.value+'/'+name)
                def exists(self):
                    if self.value.endswith('/driver'):return state['driver']
                    if self.value=='/sys/module/m7_eth2_power_hold':return state['hold']
                    return False
                def glob(self,pattern):return ['/dev/ttyRPMSG0'] if state['running'] else []
                def read_text(self):
                    if self.value.endswith('boot_id'):return 'test-boot\n'
                    if self.value.endswith('tainted'):return '4096'
                    return 'nvm0 on fixture\n m7-eth2-power-hold\n'
                def write_text(self,text):
                    calls.append(('driver',self.name));state['driver']=self.name=='bind'
            def command(*args):
                calls.append(args)
                if args[0]=='uname':return '6.12.69-gf1b67c293213'
                if args[:2]==('mcsctl','status'):return CLIENTS
                if args[0]=='insmod':
                    if kind=='insmod':raise RuntimeError('ambiguous insmod')
                    state['hold']=True
                if args[0]=='rmmod':state['hold']=False
                return ''
            def control(action,*args):
                calls.append((action,*args))
                if action=='create':state['created']=True
                elif action=='start':state['running']=True
                elif action=='stop':state['running']=False
                elif action=='rm':state['created']=False
                if action==kind:raise RuntimeError('ambiguous '+action)
            def off():
                calls.append(('OFF',))
                if state['running']:raise RuntimeError('read proof before core stopped')
            common=SimpleNamespace(command=command,control=control,confirm_up_cpus_off=off,micad_state=lambda:{'ActiveState':'active'},
                load_log_reader=lambda:None,log_header=lambda *args:(0,0),new_log_messages=lambda *args:[],
                LOG_READER=STAGE/'source/host/up_log_reader.py')
            base=SimpleNamespace(common=common,passive=SimpleNamespace(snapshot=lambda:{},compare_snapshot=Mock()),
                mmu=SimpleNamespace(verify_running=lambda image:{}),fabric=SimpleNamespace(require_fabric_clocks=lambda:0xf000),
                management=lambda:{'drift':1} if kind=='drift' and ('driver','bind') in calls else {},
                MODULE=module,MODULE_HASH=hashlib.sha256(b'fixture').hexdigest(),DRIVER=FakePath('/driver'),DEVICE=FakePath('/device'))
            def diagnostic(fd,text):
                calls.append(('diagnostic',text))
                if text=='M7 status':return runner.IDLE
                if text=='PLK status':
                    state_text=evidence()['owner']|dict(seq='0',done='0',cmd='0',processes='0',events='0')
                    return 'PLK UP2 '+' '.join(k+'='+v for k,v in state_text.items())
                if kind=='ambiguous':raise RuntimeError('ambiguous acceptance')
                return 'PLK UP2 ACCEPTED seq=1'
            def read(address,size):
                if state['running']:raise AssertionError('TCB read while CPU running')
                calls.append(('TCB',address));return memory(address,size)
            stack.enter_context(patch.dict(sys.modules,{'run_powerlink_eth_probe':base,'run_can_direct_pair':common,
                'integrated_mmu_resources':SimpleNamespace(read_reserved_dram=read),
                'termios':SimpleNamespace(TCIOFLUSH=2,tcflush=Mock()),'tty':SimpleNamespace(setraw=Mock())}))
            for name,value in dict(ROOT=root,Path=FakePath,linux_full=lambda base:(SimpleNamespace(name='eth1'),None),
                    image_symbols=lambda image:symbols,diagnostic=diagnostic).items():stack.enter_context(patch.object(runner,name,value))
            stack.enter_context(patch.object(reader,'image_symbols',return_value=symbols))
            stack.enter_context(patch.object(reader.shared,'private_reader',return_value=private))
            stack.enter_context(patch.object(runner,'read_completed',side_effect=ValueError('live proof') if kind=='liveproof' else None,return_value=report))
            stack.enter_context(patch.object(runner,'read_cold_heap',side_effect=ValueError('COLD allowance') if kind=='cold' else None,return_value=cold()))
            stack.enter_context(patch.object(runner,'finished',side_effect=RuntimeError('not complete') if kind=='fault' else None,return_value=evidence()))
            stack.enter_context(patch.object(runner.os,'geteuid',return_value=0,create=True))
            for name,value in (('O_NONBLOCK',0x10000),('O_NOCTTY',0x20000)):stack.enter_context(patch.object(runner.os,name,value,create=True))
            stack.enter_context(patch.object(runner.os,'open',return_value=123));stack.enter_context(patch.object(runner.os,'close'))
            stack.enter_context(patch.object(sys,'argv',['run','--confirm-isolated-p3j-v2-cycle','--sha256',runner.SHA]))
            with redirect_stdout(io.StringIO()):
                if kind=='normal':runner.main()
                else:
                    with self.assertRaises((RuntimeError,ValueError)):runner.main()
            if kind=='abi':
                self.assertFalse((root/'ATTEMPTED').exists() or (root/'board-result.json').exists())
                return None,calls,state
            return json.loads((root/'board-result.json').read_text()),calls,state
    def test_actual_tcb_flow_automatically_reaches_clean_linux(self):
        result,calls,state=self.workflow()
        self.assertTrue(result['passed'] and result['cleanup']);self.assertTrue(state['driver'])
        self.assertFalse(state['hold'] or state['created'] or state['running'])
        self.assertEqual(result['private_stopped']['heap_comparison']['peak_bytes'],543648)
        self.assertEqual(len(result['private_stopped']['threads']),3)
        self.assertEqual(calls.count(('diagnostic','PLK cycle-probe')),1);self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
        first_tcb=next(i for i,x in enumerate(calls) if x[0]=='TCB')
        self.assertLess(calls.index(('stop',runner.CLIENT)),first_tcb)
        self.assertLess(first_tcb,calls.index(('rm',runner.CLIENT)))
        self.assertLess(calls.index(('rm',runner.CLIENT)),calls.index(('driver','bind')))
        self.assertLess(calls.index(('driver','bind')),calls.index(('rmmod','m7_eth2_power_hold')))
    def test_wrong_tcb_abi_rejected_before_attempt_and_handoff(self):
        _,calls,state=self.workflow('abi');self.assertEqual(calls,[]);self.assertFalse(state['hold'])
    def test_fault_or_live_proof_failure_never_stops_or_restores(self):
        for kind in ('fault','liveproof','cold'):
            with self.subTest(kind=kind):
                result,calls,state=self.workflow(kind);self.assertFalse(result['cleanup']);self.assertTrue(state['hold'] and state['running'])
                self.assertNotIn(('stop',runner.CLIENT),calls);self.assertNotIn(('driver','bind'),calls)
                self.assertEqual(calls.count(('diagnostic','PLK cycle-probe')),0 if kind=='cold' else 1)
    def test_bad_actual_private_tcb_or_heap_retains_after_single_stop(self):
        for kind in ('tcb','wrapper','lease','bounds','publish','heap','exception'):
            with self.subTest(kind=kind):
                result,calls,state=self.workflow(kind);self.assertFalse(result['cleanup']);self.assertTrue(state['hold']);self.assertFalse(state['running'])
                self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
                self.assertNotIn(('rm',runner.CLIENT),calls);self.assertNotIn(('driver','bind'),calls)
    def test_ambiguous_ack_only_observes_no_resubmit(self):
        result,calls,state=self.workflow('ambiguous');self.assertFalse(result['passed']);self.assertTrue(result['cleanup'])
        self.assertEqual(calls.count(('diagnostic','PLK cycle-probe')),1);self.assertEqual(calls.count(('stop',runner.CLIENT)),1)
    def test_ambiguous_start_or_hold_retains_without_stop(self):
        for kind in ('start','insmod'):
            with self.subTest(kind=kind):
                result,calls,state=self.workflow(kind);self.assertFalse(result['cleanup'] or result['submitted'])
                self.assertNotIn(('stop',runner.CLIENT),calls);self.assertNotIn(('driver','bind'),calls)
    def test_ambiguous_stop_no_second_stop_or_private_reads(self):
        result,calls,state=self.workflow('stop');self.assertFalse(result['cleanup']);self.assertTrue(state['hold'])
        self.assertEqual(calls.count(('stop',runner.CLIENT)),1);self.assertFalse(any(x[0]=='TCB' for x in calls))
        self.assertNotIn(('driver','bind'),calls)
    def test_restore_drift_keeps_hold(self):
        result,calls,state=self.workflow('drift');self.assertFalse(result['cleanup']);self.assertTrue(state['hold'])
        self.assertNotIn(('rmmod','m7_eth2_power_hold'),calls)
    def test_no_hardware_approval_without_new_switch(self):
        with patch.object(sys,'argv',['run','--sha256',runner.SHA]),patch.object(runner.os,'open') as opened,self.assertRaises(RuntimeError):runner.main()
        opened.assert_not_called()
    def test_new_profile_marker_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runner.claim_attempt(root,'boot')
            with self.assertRaises(FileExistsError):runner.claim_attempt(root,'boot')
            self.assertIn(runner.SHA,(root/'ATTEMPTED').read_text())
    def test_old_profile_cli_and_globals_unchanged(self):
        self.assertEqual(str(historical.ROOT).replace('\\','/'),'/root/m7-powerlink-cycle-p3j-20261104')
        self.assertEqual(historical.CLIENT,'up-b-m7-plk-cycle-p3j')
        source=(STAGE/'tests/board/run_powerlink_cycle_p3j_v2_probe.py').read_text()
        self.assertEqual(source.count("diagnostic(fd, 'PLK cycle-probe')"),1)
        self.assertLess(source.index('validate_tcb_abi(json'),source.index('claim_attempt(ROOT'))
        self.assertLess(source.index('stopped = stop_completed'),source.index("common.control('rm', CLIENT)"))
if __name__=='__main__':unittest.main()
