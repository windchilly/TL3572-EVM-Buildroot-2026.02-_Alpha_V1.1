"""P4c pinned-overlay boundaries; C tests independently exercise real control code."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'build'))
import apply_m7_powerlink_cn_lifecycle as overlay
import build_m7_powerlink_cn_lifecycle as builder
from prepare_m7_powerlink import prepare
sys.path.pop(0)

class CnLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.tree=prepare(Path(cls.directory.name)/'source')
        env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(cls.tree.parent))
        subprocess.run(['git','apply','--ignore-space-change',str(STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch')],cwd=cls.tree,env=env,check=True)
        names=json.loads((overlay.OVERLAY/'upstream-files.json').read_text())
        cls.before={x:(cls.tree/x).read_bytes() for x in names}
        cls.generated=overlay.apply(cls.tree)
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()
    def source(self,name):return (self.tree/name).read_text()
    def test_locked_inputs_normalize_only_line_endings(self):
        lock=json.loads((overlay.OVERLAY/'upstream-files.json').read_text())
        self.assertEqual(len(lock),9)
        for name,raw in self.before.items():
            self.assertEqual(hashlib.sha256(raw.decode().replace('\r\n','\n').encode()).hexdigest(),lock[name])
    def test_one_shot_overlay_rejects_reapplication(self):
        with self.assertRaises(ValueError):overlay.apply(self.tree)
    def test_drift_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            tree=Path(folder)
            for name,raw in self.before.items():
                path=tree/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            changed=tree/'stack/src/user/ctrl/ctrlu.c';changed.write_bytes(changed.read_bytes()+b'/* drift */')
            with self.assertRaises(ValueError):overlay.apply(tree)
            self.assertEqual((tree/'stack/src/user/api/generic.c').read_bytes(),self.before['stack/src/user/api/generic.c'])
            self.assertFalse((tree/'stack/src/common/m7_cn_lifecycle.c').exists())
    def test_unarmed_before_target_or_ipc(self):
        text=self.source('stack/src/user/api/generic.c')
        start,end=overlay.function_span(text,'oplk_initialize');code=text[start:end]
        self.assertLess(code.index('m7_cn_lifecycle_begin()'),code.index('target_init()'))
        self.assertLess(code.index('return ret;'),code.index('target_init()'))
    def test_pending_create_and_error_retained(self):
        text=self.source('stack/src/user/api/generic.c')
        start,end=overlay.function_span(text,'oplk_create');code=text[start:end]
        self.assertLess(code.index('fStackInitialized_l = TRUE'),code.index('ctrlu_initStack'))
        self.assertIn('return m7_cn_init_result(ret)',code)
        start,end=overlay.function_span(text,'oplk_destroy')
        self.assertIn('if (ret == kErrorOk) fStackInitialized_l = FALSE',text[start:end])
    def test_all_four_selected_workers_tracked(self):
        for name,slot in (('kernel/event/eventkcal-linux.c','EVENTK'),('user/event/eventucal-linux.c','EVENTU'),
                          ('kernel/timer/hrestimer-posix.c','HRES'),('user/timer/timer-linuxuser.c','TIMERU')):
            text=self.source('stack/src/'+name)
            self.assertIn('m7_cn_thread_create(M7_CN_'+slot,text)
            self.assertIn('while (!m7_cn_stopping())',text)
            self.assertNotIn('pthread_cancel(',text);self.assertNotIn('pthread_join(',text)
            self.assertNotIn('pthread_setschedparam(',text)
    def test_timer_waits_cooperate_without_cancel(self):
        for name in ('kernel/timer/hrestimer-posix.c','user/timer/timer-linuxuser.c'):
            text=self.source('stack/src/'+name)
            self.assertIn('10000000',text);self.assertIn('sigtimedwait(',text)
            self.assertIn('if (m7_cn_stopping()) break;',text)
    def test_module_exits_are_gated(self):
        for name,func in (('kernel/event/eventkcal-linux.c','eventkcal_exit'),('user/event/eventucal-linux.c','eventucal_exit'),
                          ('kernel/timer/hrestimer-posix.c','hrestimer_exit'),('user/timer/timer-linuxuser.c','timeru_exit')):
            text=self.source('stack/src/'+name);start,end=overlay.function_span(text,func)
            code=text[start:end]
            self.assertIn('if (!m7_cn_can_release()) return kErrorInvalidOperation;',code)
            self.assertNotIn('pthread_join(',code);self.assertNotIn('pthread_cancel(',code)
    def test_ctrlu_gate_and_kernel_retval(self):
        text=self.source('stack/src/user/ctrl/ctrlu.c');start,end=overlay.function_span(text,'ctrlu_shutdownStack');code=text[start:end]
        self.assertLess(code.index('m7_cn_release_begin()'),code.index('ctrlInstance_l.fInitialized = FALSE'))
        self.assertLess(code.index('if ((tOplkError)retVal != kErrorOk)'),code.index('obdal_exit()'))
        self.assertIn('return m7_cn_release_finish()',code)
    def test_kernel_unknown_does_not_advertise_ready_or_exit(self):
        text=self.source('stack/src/kernel/ctrl/ctrlk.c')
        self.assertIn('(retVal == kErrorOk) ? kCtrlStatusReady : kCtrlStatusUnchanged',text)
        self.assertIn('(retVal == kErrorOk) ? kCtrlStatusRunning : kCtrlStatusUnchanged',text)
        self.assertIn('fExit = (retVal == kErrorOk)',text)
    def test_fixed_cn_only_profile_and_no_binary(self):
        text=self.source('stack/proj/linux/liboplkcn/oplkcfg.h')
        self.assertIn('#error P4c lifecycle supports only the fixed Linux software CN profile',text)
        self.assertIn('#error P4c lifecycle requires SOC sync',text)
        source=(STAGE/'build/build_m7_powerlink_cn_lifecycle.py').read_text()
        self.assertNotIn('demo_cn_console',source);self.assertIn("'mock-'+kind+'-tests'",source)
        self.assertEqual(len(builder.CASES),26)
        self.assertEqual(len(builder.WORKER_CASES),4)
    def test_fresh_build_required(self):
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(FileExistsError):builder.build(Path(directory))

if __name__=='__main__':unittest.main()
