"""P3c full cumulative ELF audit; zero new SIMD and timer functions retained."""
import argparse
import json
from pathlib import Path
from audit_powerlink_owner import audit, text_symbols

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "full", "toolchain", "baseline"): p.add_argument(name, type=Path)
    a = p.parse_args()
    audit(a.build, a.full, a.toolchain, a.baseline)
    prefix = str(a.toolchain / "bin/aarch64-none-elf-")
    symbols = text_symbols(prefix, a.build / "tl3572-m7-integrated-up-b.elf")
    required = {"m7_timer_probe", "m7_timer_diag_reset", "m7_timer_diag_snapshot"}
    if required - symbols: raise ValueError(f"Missing timer diagnostic: {required - symbols}")
    report = json.loads((a.build / "owner-audit.json").read_text())
    report.update(phase="P3c explicit timer-only candidate SOFTWARE AUDIT",
                  commands=report["commands"] + ["PLK timer-probe", "PLK timer-status"],
                  timer_functions=sorted(required), hardware_tested=False,
                  timer_limit="24 IRQ-gated one-shots, 100us/1ms/10ms; not worst-case latency certification")
    (a.build / "timer-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print("P3c full ELF timer diagnostic audit PASS; boot remains dormant")
