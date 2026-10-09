from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "board"))
import run_can_fd_pair as fd


def report(up, profile):
    target = 16 if up == 1 else 32
    dbtp, tdcr = (0x0D90011A, 0x35) if profile == 4 else (0x0D90031A, 0)
    text = (f"[can-irq] UP{up} before gate=0x6600 reset=0x6600 select=0x783\n"
            f"[can-irq] UP{up} counts irq=6000 txirq=3000 rxirq=3000 err=0x0 "
            f"overflow=0 wrongcpu=0 target=0x{target:x}\n"
            f"[can-fd] UP{up} config profile={profile} nbtp=0xc020c54 "
            f"dbtp=0x{dbtp:x} tdcr=0x{tdcr:x} brscfg=0x7\n")
    for stage, length, dlc in ((1, 16, 10), (2, 32, 13), (3, 64, 15)):
        info = (dlc << 24) | (1 << 21) | ((1 << 20) if profile else 0)
        text += (f"[can-fd] UP{up} stage={stage} len={length} profile={profile} "
                 f"tx={stage * 1000} rx={stage * 1000} rxinfo=0x{info:x}\n")
    return text + (f"[can-fd] UP{up} PASS profile={profile} tx=3000 rx=3000 txbytes=112000 "
                   f"rxbytes=112000 rxfd=3000 rxbrs={3000 if profile else 0} rc=0\n"
                   f"[can] UP{up} direct PASS tx=3000 rx=3000 txerr=0 rxerr=0\n")


class CanFdEvidenceTests(unittest.TestCase):
    @patch("builtins.print")
    def test_all_three_profiles(self, unused):
        for profile in (0, 2, 4):
            with patch.object(fd, "PROFILE", profile):
                fd.validate_fd_result(report(1, profile), report(2, profile))

    def test_classic_can_pass_cannot_prove_fd(self):
        with patch.object(fd, "PROFILE", 0), self.assertRaises(RuntimeError):
            fd.validate_fd_result("[can] UP1 direct PASS tx=3000 rx=3000 txerr=0 rxerr=0", report(2, 0))

    def test_missing_flags_payload_or_irq_is_rejected(self):
        for old, new in (("rxinfo=0xf300000", "rxinfo=0xf200000"),
                         ("rxinfo=0xd300000", "rxinfo=0xa300000"),
                         ("rxinfo=0xa300000", "rxinfo=0xab00000"),
                         ("rxfd=3000", "rxfd=0"), ("rxbrs=3000", "rxbrs=0"),
                         ("rxbytes=112000", "rxbytes=111999"), ("err=0x0", "err=0x40"),
                         ("txirq=3000", "txirq=2999"), ("reset=0x6600", "reset=0x0"),
                         ("dbtp=0xd90031a", "dbtp=0x0"), ("rc=0", "rc=24")):
            with self.subTest(new=new), patch.object(fd, "PROFILE", 2), self.assertRaises(RuntimeError):
                fd.validate_fd_result(report(1, 2).replace(old, new), report(2, 2))

    def test_no_brs_profile_rejects_brs_and_same_cpu(self):
        for old, new in (("rxbrs=0", "rxbrs=3000"), ("rxinfo=0xa200000", "rxinfo=0xa300000"),
                         ("target=0x10", "target=0x20")):
            with self.subTest(new=new), patch.object(fd, "PROFILE", 0), self.assertRaises(RuntimeError):
                fd.validate_fd_result(report(1, 0).replace(old, new), report(2, 0))


if __name__ == "__main__":
    unittest.main()
