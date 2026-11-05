"""P4e exact fresh overlay boundaries, independent from native mocked IO tests."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'build'))
import apply_m7_powerlink_cn_startup as overlay
import build_m7_powerlink_cn_startup as builder
from apply_m7_powerlink_cn_lifecycle import function_span
from prepare_m7_powerlink import prepare
sys.path.pop(0)

class CnStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory();cls.tree=prepare(Path(cls.directory.name)/'source')
        subprocess.run(['git','apply','--ignore-space-change',str(STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch')],
            cwd=cls.tree,env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(cls.tree.parent)),check=True)
        cls.generated=overlay.apply(cls.tree)
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()
    def source(self,path):return (self.tree/path).read_text()
    def function(self,path,name):
        text=self.source(path);start,end=function_span(text,name);return text[start:end]
    def test_fresh_destination_only(self):
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(FileExistsError):builder.build(Path(directory))
    def test_overlay_not_reapplied(self):
        with self.assertRaises(ValueError):overlay.apply(self.tree)
    def test_transport_no_admission_in_init(self):
        text=self.function('stack/src/kernel/edrv/edrv-rawsock_linux.c','edrv_init')
        self.assertIn('SOCK_CLOEXEC,0)',text);self.assertNotIn('bind(',text)
    def test_activation_owner_full_init_and_once(self):
        text=self.function('stack/src/kernel/edrv/edrv-rawsock_linux.c','m7_cn_edrv_activate')
        for value in ('m7_cn_activation_allowed()', 'pthread_equal(g.owner,pthread_self())', 'g.activation_attempted=1',
                      'now_ns()>=g.deadline', 'sll_protocol=htons(0x88ab)', 'addr.sll_ifindex=g.ifindex'):
            self.assertIn(value,text)
        self.assertEqual(text.count('bind('),1)
    def test_ready_published_only_after_successful_activate(self):
        text=self.function('stack/src/common/m7_cn_lifecycle.c','m7_cn_init_result')
        self.assertLess(text.index('m7_cn_timers_fault()'),text.index('life.stats.initialized=1'))
        self.assertLess(text.index('life.stats.initialized=1'),text.index('m7_cn_edrv_activate()'))
        self.assertLess(text.index('m7_cn_edrv_activate()'),text.index('STORE(life.ready,1)'))
        self.assertIn('life.stats.initialized=0',text)
    def test_fault_and_stop_close_gate(self):
        text=self.source('stack/src/common/m7_cn_lifecycle.c')
        self.assertEqual(text.count('STORE(life.ready,1)'),1)
        self.assertEqual(text.count('STORE(life.ready,0)'),2)
        self.assertIn('STORE(life.ready,0);STORE(life.stop,1)',text)
        self.assertNotIn('*stats=life.stats',text)
        self.assertIn('stats->first_error=LOAD(life.stats.first_error)',text)
        self.assertIn('m7_cn_fail(error);return error',self.source('stack/src/common/m7_cn_timers.c'))
    def test_tx_rx_and_pending_worker_gated(self):
        text=self.source('stack/src/kernel/edrv/edrv-rawsock_linux.c')
        self.assertEqual(text.count('if (!m7_cn_ready() || !LOAD(g.stats.active)'),2)
        self.assertLess(text.index('if (!m7_cn_ready()) {'),text.index('result=poll('))
        self.assertIn('(p.revents&POLLIN) && !LOAD(g.stop) && m7_cn_ready()',text)
    def test_pending_events_and_timers_wait_without_dispatch(self):
        for path in ('stack/src/kernel/event/eventkcal-linux.c','stack/src/user/event/eventucal-linux.c','stack/src/common/m7_cn_timers.c'):
            self.assertIn('if (!m7_cn_wait_ready()) break',self.source(path))
        for kind,name in (('kernel','eventk'),('user','eventu')):
            text=self.function('stack/src/'+kind+'/event/'+name+'.c',name+'_process')
            self.assertLess(text.index('m7_cn_ready()'),text.index('m7_cn_timer_event_current('))
    def test_event_wait_and_signal_errors_terminal(self):
        for kind,name in (('kernel','eventkcal'),('user','eventucal')):
            text=self.source('stack/src/'+kind+'/event/'+name+'-linux.c')
            self.assertIn('errno!=EINTR && errno!=ETIMEDOUT',text)
            self.assertIn('if (clock_gettime(CLOCK_MONOTONIC, &curTime))',text)
            self.assertEqual(text.count('if (sem_post('),2)
            self.assertEqual(text.count('if (ret!=kErrorOk) { m7_cn_fail(ret);break; }'),2)
    def test_active_api_gate(self):
        for name in ('oplk_execNmtCommand','oplk_process','oplk_postUserEvent'):
            self.assertIn('if (!m7_cn_ready()) return kErrorInvalidOperation',self.function('stack/src/user/api/generic.c',name))
    def test_old_profile_and_resource_code_not_rewritten(self):
        old=json.loads((STAGE/'tests/powerlink-cn-p4d-20261105/native-final/build-report.json').read_text())['generated_sha256']
        for name in ('stack/proj/linux/liboplkcn/oplkcfg.h','stack/src/common/m7_cn_private.c',
                     'stack/src/common/circbuf/circbuf-posixshm.c','stack/src/user/pdo/pdou.c',
                     'stack/src/user/ctrl/ctrlu.c','stack/src/kernel/ctrl/ctrlk.c'):
            self.assertEqual(self.generated[name],old[name])
    def test_case_counts_and_no_executable_frontend(self):
        self.assertEqual((len(builder.CONTROL_CASES),len(builder.PRIVATE_CASES),len(builder.STARTUP_CASES)),(25,25,17))
        self.assertIn('early_kernel_cleanup',builder.STARTUP_CASES)
        self.assertNotIn('demo_cn_console',(STAGE/'build/build_m7_powerlink_cn_startup.py').read_text())

if __name__=='__main__':unittest.main()
