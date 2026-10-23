"""P3h full-OD heap candidate ELF audit, not a hardware/high-water proof."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
from audit_powerlink_owner import audit, text_symbols
from audit_powerlink_eth import lse_instructions
from audit_powerlink_stack import audit as stack_audit
from verify_integrated_elf import symbols_and_data
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'full', 'toolchain', 'baseline'): p.add_argument(name, type=Path)
    a = p.parse_args(); audit(a.build, a.full, a.toolchain, a.baseline, up2_fsc=0x100000)
    prefix = str(a.toolchain / 'bin/aarch64-none-elf-')
    required = {'m7_nmt_probe', 'm7_mn_probe', 'm7_edrv_probe', 'm7_eth_probe', 'm7_timer_probe',
                'm7_timer_diag_reset', 'm7_timer_diag_snapshot'}
    candidate = a.build / 'tl3572-m7-integrated-up-b.elf'
    symbols = symbols_and_data(candidate)
    for name, size in (('snapshot', 1504), ('g_ethLease', 4), ('g_excInfoInternal', 520)):
        if symbols[name][1] != size: raise ValueError('Private cache ABI size changed: ' + name)
    if required - text_symbols(prefix, candidate): raise ValueError('Dropped cumulative diagnostic')
    if required & text_symbols(prefix, a.build / 'tl3572-m7-integrated-up-a.elf'): raise ValueError('UP1 owns UP2 diagnostic')
    assembly = subprocess.check_output([prefix + 'objdump', '-d', str(candidate)], text=True)
    if lse_instructions(assembly): raise ValueError('LSE in P3h UP2')
    commands = json.loads((a.build / 'm7-powerlink-p3h-up-b/compile_commands.json').read_text())
    bsp = [x for x in commands if x['file'].endswith('/rk3572_eth_test.c')]
    config = [x for x in commands if x['file'].endswith('/config/prt_config.c')]
    if len(bsp) != 1 or len(config) != 1: raise ValueError('Missing actual BSP/config compiler command')
    if re.findall(r'-march=(\S+)', bsp[0]['command'])[-1:] != ['armv8-a']: raise ValueError('BSP ISA changed')
    for item in bsp + config:
        if '-DM7_POWERLINK_NMT_HEAP=1' not in item['command']: raise ValueError('Missing gated heap definition')
    # Preprocess precisely the actual config.c compile command, not a synthetic header.
    args = shlex.split(config[0]['command']); index = args.index('-o'); del args[index:index+2]
    args.remove('-c'); args += ['-E', '-dM']
    macros = subprocess.check_output(args, cwd=config[0]['directory'], text=True)
    if '#define OS_MEM_FSC_PT_SIZE 0x100000' not in macros: raise ValueError('Actual memory initialization size mismatch')
    report = json.loads((a.build / 'owner-audit.json').read_text())
    stack = stack_audit(assembly)
    (a.build / 'stack-budget.json').write_text(json.dumps(stack, indent=2) + '\n')
    report.update(phase='P3h full OD, UP2 1MiB FSC, first-error SOFTWARE ONLY', hardware_tested=False,
        diagnostic_functions=sorted(required), final_up2_lse_instructions=[], rpmsg_stack_budget=stack,
        config_heap_macro='0x100000', cache_abi_changed=False, od_channels_reduced=False,
        limits='Constrained HOST allocation model plus static image proof only; actual RTOS fragmentation/peak and bounded NMT physical retest still require a new window. No updated board runner is authorized.')
    (a.build / 'nmt-heap-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('P3h cumulative full OD/actual config/heap/private image/ISA/stack audit PASS; NO BOARD')
