"""P3g final cumulative ELF audit; no board execution claim."""
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
    subprocess.run([sys.executable, str(Path(__file__).with_name('audit_powerlink_mn_probe.py')),
        str(a.build), str(a.full), str(a.toolchain), str(a.baseline)], check=True)
    prefix = str(a.toolchain / 'bin/aarch64-none-elf-')
    if 'm7_nmt_probe' not in text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-b.elf'):
        raise ValueError('Missing real bounded NMT probe')
    if 'm7_nmt_probe' in text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-a.elf'):
        raise ValueError('UP1 owns UP2 NMT diagnostic')
    commands = json.loads((a.build / 'm7-powerlink-p3g-up-b/compile_commands.json').read_text())
    bsp = [x['command'] for x in commands if x['file'].endswith('/rk3572_eth_test.c')]
    if len(bsp) != 1 or re.findall(r'-march=(\S+)', bsp[0])[-1:] != ['armv8-a']:
        raise ValueError('Wrong P3g actual BSP ISA')
    if '-DM7_POWERLINK_NMT_PROBE=1' not in bsp[0]: raise ValueError('Missing NMT gate')
    report = json.loads((a.build / 'mn-probe-audit.json').read_text())
    report.update(phase='P3g bounded reset/NotActive/SwitchOff SOFTWARE ONLY', hardware_tested=False,
        commands=report['commands'] + ['PLK nmt-probe', 'PLK nmt-status'],
        limits='32 process calls per transition, checked 1-second guard after returning calls; not a preemptive deadline for each stack call. UniProton direct PDO setup has no wait. Not real-time or MN/CN acceptance; separate physical window required.')
    report['diagnostic_functions'].append('m7_nmt_probe')
    (a.build / 'nmt-probe-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('P3g cumulative ELF/NMT/BSP ISA/stack budget audit PASS')
