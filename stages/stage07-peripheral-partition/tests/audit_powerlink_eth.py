"""P3d complete cumulative ELF audit, not a PHY or frame test."""
import argparse
import json
from pathlib import Path
from audit_powerlink_owner import audit, text_symbols

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'full', 'toolchain', 'baseline'): p.add_argument(name, type=Path)
    a = p.parse_args()
    audit(a.build, a.full, a.toolchain, a.baseline)
    symbols = text_symbols(str(a.toolchain / 'bin/aarch64-none-elf-'), a.build / 'tl3572-m7-integrated-up-b.elf')
    required = {'m7_eth_probe', 'm7_eth2_hw_lease', 'm7_eth2_hw_probe_mode', 'm7_eth2_hw_probe_stop',
                'm7_timer_probe', 'm7_timer_diag_reset', 'm7_timer_diag_snapshot'}
    if required - symbols: raise ValueError(f'Missing cumulative diagnostics: {required - symbols}')
    up1 = text_symbols(str(a.toolchain / 'bin/aarch64-none-elf-'), a.build / 'tl3572-m7-integrated-up-a.elf')
    if required & up1: raise ValueError(f'UP1 unexpectedly owns diagnostics: {required & up1}')
    report = json.loads((a.build / 'owner-audit.json').read_text())
    report.update(phase='P3d explicit no-DMA/no-frame ETH candidate SOFTWARE ONLY',
                  commands=report['commands'] + ['PLK timer-probe', 'PLK timer-status', 'PLK eth-probe', 'PLK eth-status'],
                  diagnostic_functions=sorted(required), hardware_tested=False,
                  ethernet_limit='PHY100-half/ANoff + disabled MAC mode only; no descriptors/DMA/EDRV/MN/TX')
    (a.build / 'eth-probe-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('P3d full ELF ETH+timer diagnostic audit PASS; boot remains dormant')
