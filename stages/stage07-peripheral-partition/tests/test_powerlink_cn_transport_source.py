"""P4b source/default-denial boundaries, not a hardware or stack teardown test."""
from pathlib import Path
import sys
import tempfile
import unittest
STAGE=Path(__file__).resolve().parents[1]
SOURCE=(STAGE/'source/powerlink/linux-cn/transport/edrv-m7-cn.c').read_text()
HEADER=(STAGE/'source/powerlink/linux-cn/transport/m7_cn_edrv.h').read_text()
sys.path.insert(0,str(STAGE/'build'))
import build_m7_powerlink_cn_transport as builder
sys.path.pop(0)

class CnTransportSourceTests(unittest.TestCase):
    def test_init_requires_arm_before_socket(self):
        init=SOURCE.split('tOplkError edrv_init(',1)[1].split('tOplkError edrv_exit',1)[0]
        self.assertLess(init.index('!LOAD(g.stats.armed)'),init.index('socket('))
    def test_physical_identity_and_fixed_interface(self):
        for value in ('/sys/class/net/eth2/device/driver','/sys/bus/usb/drivers/sr9900','/1-1.4.1/','strcmp(init->pDevName,"eth2")'):
            self.assertIn(value,SOURCE)
    def test_no_global_network_writes(self):
        for value in ('SIOCSIFFLAGS','SIOCSIFADDR','SIOCADDRT','system(','pthread_cancel','SCHED_FIFO'):
            self.assertNotIn(value,SOURCE)
        self.assertIn('PACKET_ADD_MEMBERSHIP',SOURCE)
    def test_io_never_blocks_or_claims_linkdown_success(self):
        for value in ('SOCK_NONBLOCK','SOCK_CLOEXEC','MSG_DONTWAIT|MSG_NOSIGNAL','MSG_DONTWAIT|MSG_TRUNC'):
            self.assertIn(value,SOURCE)
        self.assertNotIn('getLinkStatus',SOURCE)
    def test_join_before_close(self):
        exit=SOURCE.split('tOplkError edrv_exit(',1)[1].split('const UINT8*',1)[0]
        self.assertLess(exit.index('pthread_clockjoin_np'),exit.index('close_owned()'))
        self.assertIn('LOAD(g.stats.inflight)',exit)
    def test_ambiguous_close_is_exclusive(self):
        close=SOURCE.split('static int close_owned(',1)[1].split('static tOplkError init_failed',1)[0]
        self.assertLess(close.index('__atomic_exchange_n'),close.index('close(g.fd)'))
    def test_fixed_budgets_are_not_runtime_arguments(self):
        for value in ('2048U','4096U','8000000000','1000000000'):self.assertIn(value,HEADER)
    def test_rx_storage_retained_and_deferred_rejected(self):
        self.assertIn('unsigned char rx_data[1514]',SOURCE)
        self.assertIn('kEdrvReleaseRxBufferImmediately) fault(F_DEFERRED)',SOURCE)
    def test_build_output_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(FileExistsError):builder.build(Path(directory))
    def test_only_mock_test_executable_can_run(self):
        source=(STAGE/'build/build_m7_powerlink_cn_transport.py').read_text()
        self.assertIn("'mock-transport-tests'",source)
        self.assertNotIn('demo_cn_console',source)
        self.assertNotIn('ssh',source)

if __name__=='__main__':unittest.main()
