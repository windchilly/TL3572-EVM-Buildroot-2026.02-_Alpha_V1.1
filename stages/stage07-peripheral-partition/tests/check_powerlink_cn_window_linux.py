"""P4f real Linux filesystem/flock/child-process checks in fresh /tmp only.
No CN, no actual network, no board. ARM loader target is mocked on this x86
build host; readelf reads the real archived ARM ELF via a held descriptor.
"""
import json,os,shutil,stat,subprocess,sys,tempfile,time,unittest,uuid
from pathlib import Path
from unittest import mock
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
import powerlink_cn_window as window
import collect_powerlink_cn_preflight as collector
sys.path.pop(0)
BOOT=Path('/proc/sys/kernel/random/boot_id').read_text().strip() if sys.platform.startswith('linux') else None
HERE=Path(__file__).resolve()

def record():
    now=time.monotonic_ns()
    return dict(schema='m7-cn-window-v1',window_id=str(uuid.uuid4()),boot_id=BOOT,created_ns=now,expires_ns=now+2_000_000_000,
                policy_sha256='a'*64,snapshot_sha256='b'*64,artifact_sha256='c'*64)

class LinuxWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='m7-cn-p4f-');self.root=Path(self.temp.name)
        self.handles=[]
    def tearDown(self):
        for handle in self.handles:handle.close()
        self.temp.cleanup() # TEST fixture only; production module never deletes.
    def claim(self,rec=None):
        handle=window.claim(self.root,rec or record());self.handles.append(handle);return handle
    def child(self,root=None,rec=None):
        return subprocess.run([sys.executable,'-B',str(HERE),'--child',str(root or self.root),json.dumps(rec or record())],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=5)
    def test_normal_hold_and_attempt_survive_close(self):
        rec=record();handle=self.claim(rec)
        self.assertFalse(os.get_inheritable(handle.lock));self.assertFalse(os.get_inheritable(handle.directory))
        self.assertEqual(json.loads((self.root/'HOLD').read_text()),rec)
        self.assertEqual(json.loads((self.root/('ATTEMPTED-'+rec['window_id'])).read_text()),rec)
        handle.close();handle.close();self.assertTrue((self.root/'HOLD').exists())
        self.assertEqual(stat.S_IMODE((self.root/'HOLD').stat().st_mode),0o600)
    def test_concurrent_child_is_locked_out(self):
        self.claim();result=self.child();self.assertEqual(result.returncode,73,result.stderr)
        self.assertIn('BlockingIOError',result.stdout);self.assertEqual(len(list(self.root.glob('ATTEMPTED-*'))),1)
    def test_later_window_denied_after_close(self):
        self.claim().close();result=self.child();self.assertEqual(result.returncode,73,result.stderr)
        self.assertIn('FileExistsError',result.stdout);self.assertEqual(len(list(self.root.glob('ATTEMPTED-*'))),1)
    def test_child_abrupt_exit_does_not_rearm(self):
        result=self.child();self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(FileExistsError):self.claim()
        self.assertTrue((self.root/'HOLD').is_file())
    def test_symlink_directory_rejected(self):
        alias=self.root/'alias';real=self.root/'real';real.mkdir(mode=0o700);alias.symlink_to(real,target_is_directory=True)
        with self.assertRaises(OSError):window.claim(alias,record())
        self.assertEqual(list(real.iterdir()),[])
    def test_directory_permissions_rejected(self):
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):self.claim()
        self.assertEqual(list(self.root.iterdir()),[])
    def test_lock_symlink_rejected(self):
        outside=self.root/'outside';outside.write_bytes(b'original');(self.root/'LOCK').symlink_to(outside)
        with self.assertRaises(OSError):self.claim()
        self.assertEqual(outside.read_bytes(),b'original')
    def test_lock_hardlink_rejected(self):
        outside=self.root/'outside';outside.touch(mode=0o600);os.link(outside,self.root/'LOCK')
        with self.assertRaises(ValueError):self.claim()
        self.assertFalse((self.root/'HOLD').exists());self.assertEqual(outside.stat().st_nlink,2)
    def test_broken_hold_symlink_blocks(self):
        (self.root/'HOLD').symlink_to(self.root/'missing')
        with self.assertRaises(FileExistsError):self.claim()
        self.assertEqual(len(list(self.root.glob('ATTEMPTED-*'))),0)
    def test_old_attempt_without_hold_blocks_same_id(self):
        rec=record();path=self.root/('ATTEMPTED-'+rec['window_id']);path.write_bytes(b'torn previous attempt')
        with self.assertRaises(FileExistsError):self.claim(rec)
        self.assertEqual(path.read_bytes(),b'torn previous attempt');self.assertFalse((self.root/'HOLD').exists())
    def test_short_write_retains_partial_attempt(self):
        real=os.write
        with mock.patch.object(window.os,'write',side_effect=lambda fd,data:real(fd,data[:1])),self.assertRaises(ValueError):self.claim()
        files=list(self.root.glob('ATTEMPTED-*'));self.assertEqual(len(files),1);self.assertEqual(files[0].stat().st_size,1)
        self.assertFalse((self.root/'HOLD').exists())
    def test_fsync_failure_retains_attempt(self):
        with mock.patch.object(window.os,'fsync',side_effect=OSError('injected fsync failure')),self.assertRaises(OSError):self.claim()
        self.assertEqual(len(list(self.root.glob('ATTEMPTED-*'))),1);self.assertFalse((self.root/'HOLD').exists())
    def test_expired_after_fsync_retains_hold(self):
        rec=record()
        with mock.patch.object(window.time,'monotonic_ns',side_effect=[rec['created_ns'],rec['expires_ns']+1]),self.assertRaises(ValueError):self.claim(rec)
        self.assertTrue((self.root/'HOLD').exists());self.assertEqual(len(list(self.root.glob('ATTEMPTED-*'))),1)
    def test_stale_record_touches_no_files(self):
        rec=record();rec['expires_ns']=rec['created_ns']-1
        with self.assertRaises(ValueError):self.claim(rec)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_lock_permission_drift_rejected(self):
        path=self.root/'LOCK';path.touch(mode=0o644)
        with self.assertRaises(ValueError):self.claim()
        self.assertFalse((self.root/'HOLD').exists())
    def arm_file(self):
        source=STAGE/'tests/powerlink-cn-p4a-20261105/aarch64-final/demo_cn_console'
        target=self.root/'never-execute-cn';shutil.copyfile(source,target);target.chmod(0o500)
        from powerlink_cn_preflight import OLD_DEMO_SHA
        return target,OLD_DEMO_SHA
    def test_real_elf_fd_inspection_never_executes_candidate(self):
        path,digest=self.arm_file();real=subprocess.run;calls=[]
        def inspect(argv,**kwargs):
            self.assertEqual(argv[:2],['/usr/bin/readelf','--wide']);self.assertTrue(argv[-1].startswith('/proc/self/fd/'))
            self.assertEqual(len(kwargs['pass_fds']),1);calls.append(argv[2]);return real(argv,**kwargs)
        with mock.patch.object(collector.subprocess,'run',side_effect=inspect),mock.patch.object(collector.Path,'resolve',return_value=Path('/mock/arm-loader')):
            result=collector.trusted_file(str(path),digest)
        self.assertEqual(calls,['-h','-l','-d','-V']);self.assertIn('GLIBC_2.38',result['elf']['needs']['libc.so.6'])
        self.assertEqual(result['interpreter_target'],'/mock/arm-loader')
    def test_runtime_symlink_candidate_rejected(self):
        path,digest=self.arm_file();alias=self.root/'alias';alias.symlink_to(path)
        with self.assertRaises(OSError),mock.patch.object(collector.subprocess,'run',side_effect=AssertionError('no readelf')):
            collector.trusted_file(str(alias),digest)
    def test_runtime_file_changed_during_inspection_rejected(self):
        path,digest=self.arm_file();real=subprocess.run
        def inspect(argv,**kwargs):
            result=real(argv,**kwargs)
            if argv[2]=='-h':os.utime(path,ns=(1,1))
            return result
        with mock.patch.object(collector.subprocess,'run',side_effect=inspect),self.assertRaisesRegex(ValueError,'object changed'):
            collector.trusted_file(str(path),digest)
    def test_runtime_hash_mismatch_rejected_before_readelf(self):
        path,_=self.arm_file()
        with self.assertRaises(ValueError),mock.patch.object(collector.subprocess,'run',side_effect=AssertionError('no readelf')):
            collector.trusted_file(str(path),'0'*64)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':
        try:
            handle=window.claim(Path(sys.argv[2]),json.loads(sys.argv[3]));print('CLAIMED',flush=True)
            os._exit(0) # Simulates abrupt process exit: no Window.close/finalizer.
        except (OSError,ValueError) as error:
            print(type(error).__name__,str(error),flush=True);sys.exit(73)
    if not sys.platform.startswith('linux') or os.geteuid()!=0:raise RuntimeError('run only as build-host Linux root; no board')
    unittest.main(verbosity=2)
