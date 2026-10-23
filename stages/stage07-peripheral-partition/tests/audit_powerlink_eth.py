"""P3d complete cumulative ELF audit, not a PHY or frame test."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from audit_powerlink_owner import audit, text_symbols


def lse_instructions(disassembly):
    bad = []
    for line in disassembly.splitlines():
        match = re.match(r'\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+(\S+)', line)
        if match and re.fullmatch(r'(?:cas|swp|ldadd|stadd|ldclr|stclr|ldeor|steor|ldset|stset|ldsmax|stsmax|ldsmin|stsmin|ldumax|stumax|ldumin|stumin)[a-z]*', match[1]):
            bad.append(line)
    return bad


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
    prefix = str(a.toolchain / 'bin/aarch64-none-elf-')
    assembly = subprocess.check_output([prefix + 'objdump', '-d', str(a.build / 'tl3572-m7-integrated-up-b.elf')], text=True)
    if lse_instructions(assembly): raise ValueError('Unsupported LSE in final UP2: ' + str(lse_instructions(assembly)[:8]))
    commands = json.loads((a.build / 'm7-powerlink-p3d-up-b/compile_commands.json').read_text())
    bsp = [x['command'] for x in commands if x['file'].endswith('/rk3572_eth_test.c')]
    if len(bsp) != 1 or re.findall(r'-march=(\S+)', bsp[0])[-1:] != ['armv8-a'] or any(
            flag not in bsp[0] for flag in ('-mgeneral-regs-only', '-mno-outline-atomics')):
        raise ValueError('ETH BSP must override the template ARMv8.2 default; no outlined atomics')
    report = json.loads((a.build / 'owner-audit.json').read_text())
    report.update(phase='P3d explicit no-DMA/no-frame ETH candidate SOFTWARE ONLY',
                  commands=report['commands'] + ['PLK timer-probe', 'PLK timer-status', 'PLK eth-probe', 'PLK eth-status'],
                  diagnostic_functions=sorted(required), hardware_tested=False,
                  final_up2_lse_instructions=[], eth_bsp_last_march='armv8-a',
                  ethernet_limit='PHY100-half/ANoff + disabled MAC mode only; no descriptors/DMA/EDRV/MN/TX')
    (a.build / 'eth-probe-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('P3d full ELF ETH+timer diagnostic audit PASS; boot remains dormant')
