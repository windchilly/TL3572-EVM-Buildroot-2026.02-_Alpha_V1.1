"""Cumulative P3e final ELF/actual BSP ISA/diagnostic presence, not board proof."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from audit_powerlink_owner import audit, text_symbols
from audit_powerlink_eth import lse_instructions
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'full', 'toolchain', 'baseline'): p.add_argument(name, type=Path)
    a = p.parse_args(); audit(a.build, a.full, a.toolchain, a.baseline)
    prefix = str(a.toolchain / 'bin/aarch64-none-elf-')
    required = {'m7_edrv_probe', 'm7_eth_probe', 'm7_timer_probe', 'm7_timer_diag_reset', 'm7_timer_diag_snapshot'}
    symbols = text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-b.elf')
    if required - symbols: raise ValueError('Dropped diagnostic functions: ' + str(required - symbols))
    if required & text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-a.elf'): raise ValueError('UP1 owns UP2 diagnostics')
    asm = subprocess.check_output([prefix + 'objdump', '-d', str(a.build / 'tl3572-m7-integrated-up-b.elf')], text=True)
    if lse_instructions(asm): raise ValueError('Unsupported LSE in final UP2')
    commands = json.loads((a.build / 'm7-powerlink-p3e-up-b/compile_commands.json').read_text())
    bsp = [x['command'] for x in commands if x['file'].endswith('/rk3572_eth_test.c')]
    if len(bsp) != 1 or re.findall(r'-march=(\S+)', bsp[0])[-1:] != ['armv8-a']: raise ValueError('Wrong actual BSP ISA')
    report = json.loads((a.build / 'owner-audit.json').read_text())
    report.update(phase='P3e bounded EDRV diagnostic SOFTWARE ONLY', diagnostic_functions=sorted(required),
        final_up2_lse_instructions=[], hardware_tested=False,
        commands=report['commands'] + ['PLK timer-probe', 'PLK eth-probe', 'PLK edrv-probe', 'PLK edrv-status'],
        limits='One owner, 32x64B+32x1514B request/reply, 20s bound, no MN/timer acquire; NOT realtime acceptance')
    (a.build / 'edrv-probe-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('P3e cumulative final ELF/actual BSP ISA audit PASS')
