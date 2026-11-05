"""P4f synthetic replay/ELF/collector boundaries; never connects to a board."""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path,PurePosixPath
from unittest import mock
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
import powerlink_cn_preflight as gates
import collect_powerlink_cn_preflight as collector
import powerlink_cn_window as window
sys.path.pop(0)

BOOT='11111111-1111-4111-8111-111111111111'
PACKET='sk RefCnt Type Proto Iface R Rmem User Inode\n'
NOW=5_000_000_000
HEADER="""ELF Header:
  Class: ELF64
  Data: 2's complement, little endian
  Type: EXEC (Executable file)
  Machine: AArch64
"""
PROGRAM='[Requesting program interpreter: /lib/ld-linux-aarch64.so.1]\n GNU_STACK 0x0 0x0 0x0 0x0 0x0 RW 0x10\n'
DYNAMIC=' 0x1 (NEEDED) Shared library: [libc.so.6]\n'
VERSIONS="""Version needs section '.gnu.version_r' contains 1 entry:
  0000: Version: 1 File: libc.so.6 Cnt: 2
  0010: Name: GLIBC_2.17 Flags: none Version: 2
  0020: Name: GLIBC_2.38 Flags: none Version: 3
"""

def fixture():
    # Deliberately synthetic identities/artifacts, never a usable run permit.
    cn=dict(name='eth2',ifindex=17,mac='02:10:20:30:40:50',driver=gates.DRIVER,
        device='/sys/devices/fake/usb/1-1.4.1/1-1.4.1:1.0')
    management=dict(name='eth0',driver=gates.MGMT_DRIVER,mac='02:00:00:00:00:01',
        addresses=[dict(family='inet',local='192.168.2.141',prefixlen=24,scope='global')],
        routes4=[dict(dst='default',gateway='192.168.2.1',dev='eth0')],routes6=[])
    policy=dict(schema=gates.SCHEMA,runtime_ready=False,boot_id=BOOT,kernel='6.12.69-gf1b67c293213',
        namespaces=dict(net='net:[1]',pid='pid:[2]',user='user:[3]'),interface=cn,management=management,
        artifact=dict(path='/root/m7/never-built-cn',sha256='a'*64,role='bounded-cn-frontend',interpreter='/lib/ld-linux-aarch64.so.1'),
        objects={'libc.so.6':dict(path='/usr/lib64/libc-real.so',sha256='b'*64),
                 'ld-linux-aarch64.so.1':dict(path='/usr/lib64/ld-real.so',sha256='c'*64)},limits=copy.deepcopy(gates.LIMITS))
    elf=gates.elf_report(HEADER,PROGRAM,DYNAMIC,VERSIONS)
    empty=dict(interpreter=None,needed=[],needs={},definitions=[])
    libc=copy.deepcopy(empty);libc['definitions']=['GLIBC_2.17','GLIBC_2.38'];libc['needed']=['ld-linux-aarch64.so.1']
    loader=copy.deepcopy(empty)
    runtime=dict(artifact=dict(path=policy['artifact']['path'],sha256='a'*64,elf=elf,
        interpreter_target=policy['objects']['ld-linux-aarch64.so.1']['path']),objects={
            name:dict(path=obj['path'],sha256=obj['sha256'],elf=libc if name=='libc.so.6' else loader,interpreter_target=None)
            for name,obj in policy['objects'].items()})
    frame=dict(boot_id=BOOT,kernel=policy['kernel'],machine='aarch64',euid=0,cap_eff='00002000',
        namespaces=copy.deepcopy(policy['namespaces']),environment={},interface=copy.deepcopy(cn),
        links=[dict(ifname='eth2',ifindex=17,address=cn['mac'],link_type='ether',mtu=1500,operstate='UP',
            flags=['BROADCAST','MULTICAST','UP','LOWER_UP'],promiscuity=0)],addresses=[],routes4=copy.deepcopy(management['routes4']),routes6=[],
        packet=PACKET,processes=[dict(pid=123,start=100,exe='/usr/bin/python3',argv=['python3','collect_powerlink_cn_preflight.py'])],
        tc_ingress=[],tc_egress=[],management=copy.deepcopy(management),runtime=runtime,start_ns=4_000_000_000,end_ns=4_100_000_000)
    second=copy.deepcopy(frame);second.update(start_ns=4_200_000_000,end_ns=4_300_000_000)
    return policy,dict(schema=gates.SCHEMA,frames=[frame,second])

def set_at(value,path,replacement):
    for field in path[:-1]:value=value[field]
    value[path[-1]]=replacement

class PreflightTests(unittest.TestCase):
    def test_positive_is_evidence_never_execution(self):
        policy,snapshot=fixture();result=gates.check(snapshot,policy,NOW)
        self.assertTrue(result['preflight_pass']);self.assertFalse(result['runtime_ready']);self.assertFalse(result['execution_allowed'])
        self.assertEqual(result['snapshot_sha256'],gates.sha(snapshot))
    def test_strict_json(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            with self.subTest(text=text),self.assertRaises(ValueError):gates.unique_json(text)
    def test_template_refuses_before_collection(self):
        with mock.patch.object(collector,'collect_frame',side_effect=AssertionError('no collector')),self.assertRaises(ValueError):
            collector.policy_check(json.loads((STAGE/'config/powerlink-cn-preflight.template.json').read_text()))
    def test_real_archived_cn_elf_versions_are_exact(self):
        root=STAGE/'tests/powerlink-cn-p4a-20261105/aarch64-final'
        elf=gates.elf_report((root/'elf-header.txt').read_text(),'[Requesting program interpreter: /lib/ld-linux-aarch64.so.1]',
            (root/'elf-dynamic.txt').read_text(),(root/'elf-versions.txt').read_text())
        self.assertEqual(set(elf['needs']['libc.so.6']),{'GLIBC_2.17','GLIBC_2.32','GLIBC_2.34','GLIBC_2.38'})
        policy,snapshot=fixture()
        for frame in snapshot['frames']:frame['runtime']['artifact']['elf']=elf
        with self.assertRaisesRegex(ValueError,'missing symbol versions'):gates.check(snapshot,policy,NOW)
    def test_packet_unrelated_port_allowed(self):
        policy,snapshot=fixture()
        for frame in snapshot['frames']:frame['packet']+= '0000000000000000 3 3 0003 2 1 0 0 1234\n'
        self.assertTrue(gates.check(snapshot,policy,NOW)['preflight_pass'])
    def test_packet_malformed_rows_denied(self):
        for data in ('',PACKET+'bad\n',PACKET+'0 3 3 88AB 17 1 0 0 0\n',PACKET+'0 3 3 nope 17 1 0 0 12\n'):
            with self.subTest(data=data),self.assertRaises(ValueError):gates.packet_table(data)
    def test_packet_duplicate_inode_denied(self):
        line='0 3 3 88ab 2 1 0 0 1234\n'
        with self.assertRaises(ValueError):gates.packet_table(PACKET+line+line)
    def test_clock_order_and_age(self):
        for now in (4_000_000_000,7_000_000_000,True):
            policy,snapshot=fixture()
            with self.subTest(now=now),self.assertRaises(ValueError):gates.check(snapshot,policy,now)
    def test_second_observation_drift_denied(self):
        policy,snapshot=fixture();snapshot['frames'][1]['processes'][0]['start']+=1
        with self.assertRaisesRegex(ValueError,'state changed'):gates.check(snapshot,policy,NOW)
    def test_historical_sysfs_device_shape_not_net_subdirectory(self):
        historical=json.loads((STAGE/'tests/board/eth3-recovery-20261009/final.json').read_text())
        policy,snapshot=fixture();device=historical['networks']['eth2']['device']
        policy['interface']['device']=device
        for frame in snapshot['frames']:frame['interface']['device']=device
        self.assertTrue(gates.check(snapshot,policy,NOW)['preflight_pass'])
    def test_dependency_version_not_numeric_maximum(self):
        policy,snapshot=fixture()
        for frame in snapshot['frames']:frame['runtime']['objects']['libc.so.6']['elf']['definitions']=['GLIBC_2.99']
        with self.assertRaisesRegex(ValueError,'missing symbol versions'):gates.check(snapshot,policy,NOW)
    def test_elf_missing_count_rejected(self):
        with self.assertRaises(ValueError):gates.elf_report(HEADER,PROGRAM,DYNAMIC,VERSIONS.replace('Cnt: 2','Cnt: 3'))
    def test_elf_version_symbols_do_not_supply_definitions(self):
        versions="Version symbols section '.gnu.version' contains 2 entries:\n 000: 2 (GLIBC_2.38)\n"
        self.assertEqual(gates.elf_report(HEADER,PROGRAM,DYNAMIC,versions)['definitions'],[])
    def test_elf_architecture_and_injection_rejected(self):
        for header,program,dynamic in ((HEADER.replace('AArch64','X86-64'),PROGRAM,DYNAMIC),
            (HEADER,PROGRAM.replace(' RW ',' RWE '),DYNAMIC),(HEADER,PROGRAM,DYNAMIC+' 0x1 (RUNPATH) Library runpath: [/tmp]\n'),
            (HEADER,PROGRAM,DYNAMIC+' 0x1 (AUDIT) Audit library: [evil.so]\n'),
            (HEADER,PROGRAM,DYNAMIC.replace('libc.so.6','/tmp/libc.so.6'))):
            with self.subTest(dynamic=dynamic),self.assertRaises(ValueError):gates.elf_report(header,program,dynamic,VERSIONS)
    def test_readonly_command_boundary(self):
        with mock.patch.object(subprocess,'run',side_effect=AssertionError('execution forbidden')):
            for argv in (['ldd','/tmp/cn'],['/lib/ld-linux-aarch64.so.1','--list','/tmp/cn'],['/tmp/cn','--help'],
                         ['/sbin/ip','link','set','eth2','down'],['/sbin/tc','qdisc','del','dev','eth2','root']):
                with self.subTest(argv=argv),self.assertRaises(ValueError):collector.command(argv)
    def test_replay_never_collects_or_opens_socket(self):
        policy,snapshot=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'policy.json').write_text(json.dumps(policy));(root/'snapshot.json').write_text(json.dumps(snapshot))
            argv=['collect','--policy',str(root/'policy.json'),'--replay',str(root/'snapshot.json'),'--now-ns',str(NOW)]
            with (mock.patch.object(sys,'argv',argv),mock.patch.object(collector,'collect_frame',side_effect=AssertionError('live')),
                  mock.patch.object(subprocess,'run',side_effect=AssertionError('process')),mock.patch('builtins.print') as output):
                collector.main()
            result=json.loads(output.call_args.args[0]);self.assertEqual(result['mode'],'offline-replay');self.assertFalse(result['result']['execution_allowed'])
    def test_window_record_freshness_and_binding(self):
        record=dict(schema='m7-cn-window-v1',window_id=BOOT,boot_id=BOOT,created_ns=4_000_000_000,expires_ns=6_000_000_000,
            policy_sha256='a'*64,snapshot_sha256='b'*64,artifact_sha256='c'*64)
        window.record_check(record,BOOT,NOW)
        for boot,now in ((BOOT,6_000_000_001),('22222222-2222-4222-8222-222222222222',NOW),(BOOT,False)):
            with self.subTest(boot=boot,now=now),self.assertRaises(ValueError):window.record_check(record,boot,now)
    def test_window_has_no_execution_or_recovery_cli(self):
        text=(STAGE/'tests/board/powerlink_cn_window.py').read_text()
        for value in ('subprocess','socket.socket','unlink(', 'rmtree(', 'truncate(', 'def main('):self.assertNotIn(value,text)
    def test_collector_reads_only_exact_allowlisted_commands(self):
        policy,snapshot=fixture();expected=snapshot['frames'][0];calls=[]
        def output(argv,**kwargs):
            calls.append(argv);self.assertNotIn('shell',kwargs)
            if argv[0]=='/sbin/tc':value=[]
            elif 'link' in argv:value=expected['links']
            elif 'address' in argv:value=[dict(ifname=argv[-1],addr_info=[] if argv[-1]=='eth2' else policy['management']['addresses'])]
            elif '-4' in argv:value=expected['routes4']
            else:value=[]
            return subprocess.CompletedProcess(argv,0,json.dumps(value).encode(),b'')
        def contents(path,limit=262144):
            path=Path(path).as_posix()
            if path.endswith('boot_id'):return BOOT
            if path=='/proc/self/status':return 'CapEff:\t00002000\n'
            if path=='/proc/net/packet':return PACKET
            if path.endswith('ifindex'):return '17' if '/eth2/' in path else '2'
            if path.endswith('address'):return policy['interface']['mac'] if '/eth2/' in path else policy['management']['mac']
            raise AssertionError('unexpected read '+path)
        def resolved(path,strict=False):
            path=Path(path).as_posix();requirement=policy['interface'] if '/eth2/' in path else policy['management']
            return PurePosixPath(requirement['driver'] if path.endswith('driver') else policy['interface']['device'])
        def runtime(path,digest):
            if path==policy['artifact']['path']:return expected['runtime']['artifact']
            return next(x for x in expected['runtime']['objects'].values() if x['path']==path)
        with (mock.patch.object(collector.subprocess,'run',side_effect=output),mock.patch.object(collector,'read',side_effect=contents),
              mock.patch.object(collector.os,'readlink',side_effect=lambda path:policy['namespaces'][str(path).rsplit('/',1)[1]]),
              mock.patch.object(collector.Path,'resolve',autospec=True,side_effect=resolved),mock.patch.object(collector,'trusted_file',side_effect=runtime),
              mock.patch.object(collector,'processes',return_value=expected['processes']),mock.patch.object(collector.os,'geteuid',create=True,return_value=0),
              mock.patch.object(collector.platform,'machine',return_value='aarch64'),mock.patch.object(collector.platform,'release',return_value=policy['kernel']),
              mock.patch.object(collector.time,'monotonic_ns',side_effect=[4_000_000_000,4_100_000_000]),mock.patch.dict(os.environ,{},clear=True)):
            observed=collector.collect_frame(policy)
        self.assertEqual(observed,expected);self.assertEqual(len(calls),7)
    def process_census(self,changed_start=False,vanished=False):
        fields=['S']+['0']*50;fields[19]='400';before='7 (name with () spaces) '+' '.join(fields)
        fields[11]='99';fields[19]='401' if changed_start else '400';after='7 (name with () spaces) '+' '.join(fields)
        stat_reads=iter([before,after])
        def contents(path,limit=262144):return next(stat_reads) if Path(path).as_posix().endswith('/stat') else 'service\0'
        with (mock.patch.object(collector.Path,'iterdir',return_value=iter([Path('/proc/7')])) as listing,
              mock.patch.object(collector,'read',side_effect=contents),
              mock.patch.object(collector.os,'readlink',side_effect=FileNotFoundError() if vanished else None,return_value='/usr/bin/service')):
            # iterdir returns a fresh iterator on each enumeration.
            listing.side_effect=lambda:iter([Path('/proc/7')]);return collector.processes()
    def test_process_cpu_stat_changes_not_pid_reuse(self):
        self.assertEqual(self.process_census()[0]['start'],400)
    def test_process_pid_reuse_denied(self):
        with self.assertRaisesRegex(ValueError,'PID reused'):self.process_census(changed_start=True)
    def test_process_disappearance_denied(self):
        with self.assertRaisesRegex(ValueError,'vanished/hidden'):self.process_census(vanished=True)

FRAME_MUTATIONS={
    'nonroot':(('euid',),1),'missing_cap_net_raw':(('cap_eff',),'00000000'),
    'wrong_boot':(('boot_id',),'22222222-2222-4222-8222-222222222222'),
    'wrong_namespace':(('namespaces','net'),'net:[999]'),'loader_environment':(('environment',),{'LD_PRELOAD':'evil'}),
    'wrong_mac':(('interface','mac'),'02:00:00:00:00:99'),'wrong_driver':(('interface','driver'),gates.MGMT_DRIVER),
    'ipv4_address':(('addresses',),[dict(family='inet',local='10.0.0.1')]),
    'ipv6_link_local':(('addresses',),[dict(family='inet6',local='fe80::1')]),
    'ipv6_route':(('routes6',),[dict(dst='fe80::/64',dev='eth2')]),
    'multipath_route':(('routes4',),[dict(dst='default',nexthops=[dict(dev='eth2',gateway='10.0.0.1')])]),
    'bridge':(('links',0,'master'),'br0'),'xdp':(('links',0,'xdp'),{'attached':'driver'}),
    'promiscuous':(('links',0,'promiscuity'),1),'wrong_mtu':(('links',0,'mtu'),9000),
    'tc_ingress':(('tc_ingress',),[dict(kind='bpf')]),'tc_egress_unknown':(('tc_egress',),None),
    'all_packet':(('packet',),PACKET+'0 3 3 0003 0 1 0 0 1234\n'),
    'prepared_protocol_zero':(('packet',),PACKET+'0 3 3 0000 0 0 0 0 1234\n'),
    'target_packet':(('packet',),PACKET+'0 3 3 88ab 17 1 0 0 1234\n'),
    'management_changed':(('management','routes4'),[]),'runtime_wrong_hash':(('runtime','artifact','sha256'),'d'*64),
    'runtime_missing_version':(('runtime','objects','libc.so.6','elf','definitions'),['GLIBC_2.17']),
    'runtime_nested_dependency':(('runtime','objects','libc.so.6','elf','needed'),['libm.so.6']),
    'conflicting_process':(('processes',0,'exe'),'/usr/bin/tcpdump'),
    'pid_reuse_type':(('processes',0,'start'),True),
}
POLICY_MUTATIONS={
    'budget':(('limits','max_tx'),2049),'management_alias':(('interface','name'),'eth0'),
    'wrong_usb':(('interface','device'),'/sys/devices/fake/1-1.4.10/net/eth2'),
    'unbounded_renamed_demo':(('artifact','sha256'),gates.OLD_DEMO_SHA),
    'incomplete_artifact':(('artifact','path'),None),'runtime_ready':(('runtime_ready',),True),
}
def mutation_test(path,value,policy_mutation=False):
    def test(self):
        policy,snapshot=fixture()
        if policy_mutation:set_at(policy,path,copy.deepcopy(value))
        else:
            for frame in snapshot['frames']:set_at(frame,path,copy.deepcopy(value))
        with self.assertRaises(ValueError):gates.check(snapshot,policy,NOW)
    return test
for name,(path,value) in FRAME_MUTATIONS.items():setattr(PreflightTests,'test_reject_'+name,mutation_test(path,value))
for name,(path,value) in POLICY_MUTATIONS.items():setattr(PreflightTests,'test_policy_reject_'+name,mutation_test(path,value,True))
if __name__=='__main__':unittest.main()
