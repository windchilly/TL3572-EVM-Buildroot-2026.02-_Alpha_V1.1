"""P4d source/build boundaries; production C and passive stack run independently."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'build'))
import apply_m7_powerlink_cn_private as overlay
import build_m7_powerlink_cn_private as builder
from apply_m7_powerlink_cn_lifecycle import function_span
from prepare_m7_powerlink import prepare
sys.path.pop(0)

class CnPrivateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.tree=prepare(Path(cls.directory.name)/'source')
        env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(cls.tree.parent))
        subprocess.run(['git','apply','--ignore-space-change',str(STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch')],cwd=cls.tree,env=env,check=True)
        cls.original={name:(cls.tree/name).read_bytes() for name in overlay.RAW}
        cls.generated=overlay.apply(cls.tree)
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()
    def source(self,name):return (self.tree/name).read_text()
    def test_fresh_build_required(self):
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(FileExistsError):builder.build(Path(directory))
    def test_raw_drift_rejected_before_p4c_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            tree=Path(folder);path=tree/overlay.RAW[0];path.parent.mkdir(parents=True)
            path.write_bytes(self.original[overlay.RAW[0]]+b'/* drift */')
            with self.assertRaises(ValueError):overlay.apply(tree)
            self.assertFalse((tree/'stack/src/common/m7_cn_lifecycle.c').exists())
    def test_immutable_p4c_generic_and_profile_retained(self):
        old=json.loads((STAGE/'tests/powerlink-cn-p4c-20261105/native-final/build-report.json').read_text())['generated_sha256']
        for name in ('stack/src/user/api/generic.c','stack/src/user/ctrl/ctrlu.c','stack/src/kernel/ctrl/ctrlk.c','stack/proj/linux/liboplkcn/oplkcfg.h'):
            self.assertEqual(self.generated[name],old[name])
    def test_no_named_ipc_in_selected_modules(self):
        for name in ('stack/src/common/m7_cn_private.c','stack/src/common/circbuf/circbuf-posixshm.c',
                     'stack/src/kernel/event/eventkcal-linux.c','stack/src/user/event/eventucal-linux.c'):
            text=self.source(name)
            for forbidden in ('sem_open(', 'sem_unlink(', 'sem_close(', 'shm_open(', 'shm_unlink('):self.assertNotIn(forbidden,text)
    def test_process_private_semaphore_owner(self):
        text=self.source('stack/src/common/m7_cn_private.c')
        self.assertIn('sem_init(&events.user,0,0)',text);self.assertIn('sem_init(&events.kernel,0,0)',text)
        self.assertIn('!events.user_detached || events.exit_attempted',text)
        self.assertIn('if (!m7_cn_can_release()',text)
    def test_bounded_refcounted_heap_buffers(self):
        text=self.source('stack/src/common/circbuf/circbuf-posixshm.c')
        for value in ('pool[NR_OF_CIRC_BUFFERS]','pool[id].refs<2','pool[id].closing','*size>1048576U','--pool[id].refs==0'):
            self.assertIn(value,text)
        self.assertNotIn('mmap(',text);self.assertNotIn('close(',text)
    def test_count_and_signal_access_locked(self):
        text=self.source('stack/src/common/circbuf/circbuffer.c')
        self.assertIn('circbuf_lock((tCircBufInstance*)pInstance_p)',text)
        self.assertEqual(text.count('VOIDFUNCPTR signal = pInstance_p->pfnSigCb;'),2)
        self.assertEqual(text.count('if (signal != NULL) signal();'),2)
    def test_queue_indices_reject_negative_and_end(self):
        for kind,count in (('kernel',7),('user',6)):
            name='eventkcalintf' if kind=='kernel' else 'eventucalintf'
            text=self.source('stack/src/'+kind+'/event/'+name+'-circbuf.c')
            self.assertEqual(text.count('(unsigned)eventQueue_p >= (unsigned)kEventQueueNum'),count)
    def test_monotonic_event_waits(self):
        for kind,name in (('kernel','eventkcal'),('user','eventucal')):
            text=self.source('stack/src/'+kind+'/event/'+name+'-linux.c')
            self.assertIn('sem_clockwait(',text);self.assertNotIn('CLOCK_REALTIME',text)
            self.assertNotIn('sem_timedwait(',text)
    def test_old_signal_timer_sources_excluded(self):
        cmake=self.source('stack/proj/linux/liboplkcn/CMakeLists.txt')
        self.assertIn('LIST(REMOVE_ITEM LIB_SOURCES ${KERNEL_SOURCE_DIR}/timer/hrestimer-posix.c ${USER_SOURCE_DIR}/timer/timer-linuxuser.c)',cmake)
        text=self.source('stack/src/common/m7_cn_timers.c')
        for forbidden in ('timer_create(', 'timer_settime(', 'sigtimedwait(', 'malloc(', 'free(', 'pthread_cancel('):self.assertNotIn(forbidden,text)
        self.assertIn('pthread_condattr_setclock(&attr,CLOCK_MONOTONIC)',text)
    def test_generation_keys_and_bounded_slots(self):
        text=self.source('stack/src/common/m7_cn_timers.c')
        self.assertIn('#define USER_SLOTS 64U',text);self.assertIn('UINT64_MAX>>9',text)
        self.assertIn('timers->timers[index-1].handle!=handle',text)
        self.assertIn('snapshot=*due',text);self.assertIn('timer->fired=0',text)
    def test_stale_events_gated_before_dispatch(self):
        for name,func in (('kernel/event/eventk.c','eventk_process'),('user/event/eventu.c','eventu_process')):
            text=self.source('stack/src/'+name);start,end=function_span(text,func);code=text[start:end]
            self.assertLess(code.index('m7_cn_timer_event_current(pEvent_p)'),code.index('switch (pEvent_p->eventSink)'))
    def test_private_fault_blocks_init_and_release(self):
        text=self.source('stack/src/common/m7_cn_lifecycle.c')
        self.assertEqual(text.count('m7_cn_timers_fault()'),4)
        self.assertLess(text.index('m7_cn_timers_fault()'),text.index('life.stats.initialized=1'))
        self.assertIn('if (sem_destroy(pLockSem)) { m7_cn_fail(kErrorInvalidOperation); return; }',self.source('stack/src/arch/linux/target-mutex.c'))
        self.assertIn('if (stats.first_error != kErrorOk) return stats.first_error',self.source('stack/src/user/pdo/pdou.c'))
    def test_no_global_ftrace_or_timer_signal_setup(self):
        text=self.source('stack/src/arch/linux/target-linux.c')
        for func in ('target_init','target_cleanup'):
            start,end=function_span(text,func);code=text[start:end]
            self.assertNotIn('pthread_sigmask(',code);self.assertNotIn('FTRACE_',code)
    def test_component_counts_and_no_peer(self):
        self.assertEqual((len(builder.CONTROL_CASES),len(builder.PRIVATE_CASES),len(builder.STACK_CASES)),(26,25,4))
        for name in ('sem_open','shm_open','timer_create'):self.assertIn(name,builder.FORBIDDEN)
        self.assertNotIn('demo_cn_console',(STAGE/'build/build_m7_powerlink_cn_private.py').read_text())
    def test_overlay_cannot_be_reapplied(self):
        with self.assertRaises(ValueError):overlay.apply(self.tree)

if __name__=='__main__':unittest.main()
