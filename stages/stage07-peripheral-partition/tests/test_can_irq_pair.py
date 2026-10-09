#!/usr/bin/env python3
"""IRQ evidence must include autonomous setup and both hardware completions."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "board"))
import run_can_irq_pair as irq


def report(up, target):
    return (f"[can-irq] UP{up} before gate=0x6600 reset=0x6600 select=0x783\n"
            f"[can-irq] UP{up} counts irq=20000 txirq=10000 rxirq=10000 err=0x0 "
            f"overflow=0 wrongcpu=0 target=0x{target:x} status=0x20002\n"
            f"[can] UP{up} direct PASS tx=10000 rx=10000 txerr=0 rxerr=0 state=0x0 rc=0\n")


class CanIrqEvidenceTests(unittest.TestCase):
    @patch("builtins.print")
    def test_complete_evidence_passes(self, unused):
        irq.validate_irq_result(report(1, 16), report(2, 32))

    def test_polling_pass_is_insufficient(self):
        with self.assertRaises(RuntimeError):
            irq.validate_irq_result("[can] UP1 direct PASS tx=10000 rx=10000", report(2, 32))

    def test_same_cpu_target_is_rejected(self):
        with self.assertRaises(RuntimeError):
            irq.validate_irq_result(report(1, 16), report(2, 16))

    def test_missing_interrupt_or_error_is_rejected(self):
        for old, new in (("txirq=10000", "txirq=9999"), ("rxirq=10000", "rxirq=0"),
                         ("err=0x0", "err=0x40"), ("wrongcpu=0", "wrongcpu=1"),
                         ("txerr=0", "txerr=1"), ("reset=0x6600", "reset=0x0")):
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                irq.validate_irq_result(report(1, 16).replace(old, new), report(2, 32))


if __name__ == "__main__":
    unittest.main()
