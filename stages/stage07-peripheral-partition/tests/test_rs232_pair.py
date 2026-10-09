import contextlib
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent / "board"))
import rs232_resources as resources
import run_rs232_pair as runner


def transcript(up, baud=115200, target=None):
    p = resources.RESOURCES["up-a" if up == 1 else "up-b"]
    target = target or (0x10 if up == 1 else 0x20)
    divisor = {115200: 13, 38400: 39, 9600: 156}[baud]
    return (f"[rs232] UP{up} before pgate=0x{p['p_mask']:x} sgate=0x{p['s_mask']:x} "
            f"preset=0x{p['p_mask']:x} sreset=0x{p['s_mask']:x} select=0x30f\n"
            f"[rs232] UP{up} ready uart={p['uart']} mpidr=0x{0x100 + up - 1:x} "
            f"intid={p['spi'] + 32} target=0x{target:x} baud={baud} clock=24000000 divisor={divisor} lcr=0x3\n"
            f"[rs232] UP{up} counts irq=64000 txirq=33000 rxirq=32000 txbytes=32000 rxbytes=32000 "
            f"err=0x0 overflow=0 wrongcpu=0 busy=0 storm=0 target=0x{target:x}\n"
            f"[rs232] UP{up} direct PASS baud={baud} tx=1000 rx=1000 bytes=32 rc=0\n")


class Rs232Tests(unittest.TestCase):
    def validate(self, a, b, baud=115200):
        with contextlib.redirect_stdout(io.StringIO()):
            runner.validate_result(a, b, baud)

    def test_profiles(self):
        for baud in (115200, 38400, 9600):
            self.validate(transcript(1, baud), transcript(2, baud), baud)

    def test_reject_corrupt_reports(self):
        a, b = transcript(1), transcript(2)
        for old, new in (("txbytes=32000", "txbytes=31999"), ("rxbytes=32000", "rxbytes=32001"),
                         ("err=0x0", "err=0x2"), ("wrongcpu=0", "wrongcpu=1"),
                         ("overflow=0", "overflow=1"), ("busy=0", "busy=1"),
                         ("storm=0", "storm=1"), ("divisor=13", "divisor=12"),
                         ("txirq=33000", "txirq=0"), ("select=0x30f", "select=0x300"),
                         ("preset=0x80", "preset=0x0"), ("tx=1000", "tx=999"),
                         ("lcr=0x3", "lcr=0x13"), ("uart=4", "uart=3"),
                         ("mpidr=0x100", "mpidr=0x101")):
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                self.validate(a.replace(old, new), b)

    def test_same_target_rejected(self):
        with self.assertRaises(RuntimeError):
            self.validate(transcript(1), transcript(2, target=0x10))

    def test_physical_mapping_and_owned_masks(self):
        a, b = resources.RESOURCES.values()
        self.assertEqual((a["uart"], b["uart"]), (4, 8))
        self.assertEqual((a["spi"] + 32, b["spi"] + 32), (160, 164))
        self.assertEqual(resources.owned_masks()[resources.CRU + 0x838], 0x880)
        self.assertEqual((a["mux"], b["mux"]), (0x2607400C, 0x26074010))
        self.assertIn("UART3", b["physical"])

    def test_decode_disabled(self):
        for p in resources.RESOURCES.values():
            values = {address: 0 for address in resources.owned_masks()}
            values.update({address: 0 for address in resources.gic_addresses(p["spi"] + 32).values()})
            values[resources.CRU + 0x838] = p["p_mask"]
            values[resources.CRU + 0xA38] = p["p_mask"]
            values[p["s_gate"]] = p["s_mask"]
            values[p["s_reset"]] = p["s_mask"]
            values[p["select"]] = 0x30F
            values[p["mux"]] = p["mux_value"]
            decoded = resources.decode(p, values)
            self.assertTrue(all(decoded[k] for k in ("p_gated", "s_gated", "p_reset", "s_reset", "mux_ok")))
            self.assertEqual((decoded["source"], decoded["divider"]), (3, 16))
            self.assertFalse(any(decoded[k] for k in ("enabled", "pending", "active", "edge")))


if __name__ == "__main__":
    unittest.main()
