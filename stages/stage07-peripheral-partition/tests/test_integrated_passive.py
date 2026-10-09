import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent / 'board'))
import run_integrated_passive as runner


class PassiveTests(unittest.TestCase):
    def test_forbid_run_before_any_write(self):
        for command in ('M7 run can 1', 'M7 run rs232 115200', 'M7 run all 115200 4',
                        'M7 status\nM7 run can 1', '', 'M7 status\x00'):
            with self.assertRaises(ValueError):
                runner.passive_command(-1, command)

    def test_only_zero_jobs_status_accepted(self):
        text = 'M7 UP1 ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0'
        runner.validate_status(text, 1)
        for old, new in (('ready=1', 'ready=0'), ('done=0/0/0', 'done=1/0/0'),
                         ('pending=0x0', 'pending=0x1'), ('running=0x0', 'running=0x4'),
                         ('rc=0/0/0', 'rc=0/30/0'), ('UP1', 'UP2')):
            with self.assertRaises(RuntimeError):
                runner.validate_status(text.replace(old, new), 1)

    def test_boot_rejects_any_peripheral_entry(self):
        text = ('[boot] UP CPU4 entered\n[boot] interrupt routing ready\n'
                '[boot] MMU PASS sctlr=0x30d01805 tables=9/16 mapped=48 ttbr=0x7ba00000\n'
                '[boot] scheduler task entered\n[boot] RPMsg ready\n'
                '[integrated] UP1 ready modules=can-classic,can-fd,rs232,rs485 mode=passive\n')
        runner.validate_boot(text, 1)
        for extra in ('[can-irq] UP1 before', '[rs485] UP1 ready', '[integrated] UP1 begin module=0'):
            with self.assertRaises(RuntimeError):
                runner.validate_boot(text + extra, 1)
        with self.assertRaises(RuntimeError):
            runner.validate_boot(text.replace('[boot] RPMsg ready', ''), 1)
        for old, new in (('sctlr=0x30d01805', 'sctlr=0x30d00800'), ('tables=9/16', 'tables=8/16'),
                         ('mapped=48', 'mapped=47'), ('ttbr=0x7ba00000', 'ttbr=0x7ca00000')):
            with self.assertRaises(RuntimeError):
                runner.validate_boot(text.replace(old, new), 1)

    def test_resource_drift_fails(self):
        initial = {'registers': {'0x2609082c': 1}, 'drivers': {'test.serial': 'dw-apb-uart'}}
        runner.compare_snapshot(initial, initial)
        with self.assertRaises(RuntimeError):
            runner.compare_snapshot(initial, {'registers': {'0x2609082c': 0}, 'drivers': initial['drivers']})


if __name__ == '__main__':
    unittest.main()
