"""P3f final ELF and actual BSP compiler audit; no hardware claim."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from audit_powerlink_owner import text_symbols
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'full', 'toolchain', 'baseline'): p.add_argument(name, type=Path)
    a = p.parse_args()
    subprocess.run([sys.executable, str(Path(__file__).with_name('audit_powerlink_edrv_probe.py')),
        str(a.build), str(a.full), str(a.toolchain), str(a.baseline)], check=True)
    prefix = str(a.toolchain / 'bin/aarch64-none-elf-')
    if 'm7_mn_probe' not in text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-b.elf'):
        raise ValueError('Missing real full-stack lifecycle probe')
    if 'm7_mn_probe' in text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-a.elf'):
        raise ValueError('UP1 owns UP2 lifecycle')
    commands = json.loads((a.build / 'm7-powerlink-p3f-up-b/compile_commands.json').read_text())
    bsp = [x['command'] for x in commands if x['file'].endswith('/rk3572_eth_test.c')]
    if len(bsp) != 1 or re.findall(r'-march=(\S+)', bsp[0])[-1:] != ['armv8-a']: raise ValueError('Wrong P3f actual BSP ISA')
    report = json.loads((a.build / 'edrv-probe-audit.json').read_text())
    report.update(phase='P3f full-stack GsOff lifecycle SOFTWARE ONLY', hardware_tested=False,
        commands=report['commands'] + ['PLK mn-probe', 'PLK mn-status'],
        limits='128 process calls/2-second guard; full stack remains GsOff, no NMT reset/start/CN or real-time acceptance')
    report['diagnostic_functions'].append('m7_mn_probe')
    (a.build / 'mn-probe-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('P3f cumulative ELF/full-stack lifecycle/BSP ISA audit PASS')
