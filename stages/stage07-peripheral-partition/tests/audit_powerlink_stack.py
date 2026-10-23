"""Pinned 4-KiB RPMsg TTY critical logging path + explicit 1-KiB reserve.
Not a universal WC stack bound: FP formats/other paths/preemption need more work.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
CHAIN = ('rpmsg_tty_task', 'Rk3572IntegratedInput', 'Rk3572PowerlinkInput', 'PRT_Printf',
         'UpLogVprintf', 'vsnprintf_s', 'SecVsnprintfImpl', 'SecOutput')
def functions(assembly):
    result = {}; current = None
    for line in assembly.splitlines():
        header = re.match(r'^\s*[0-9a-f]+ <([^>]+)>:$', line)
        if header: current = header[1]; result[current] = []
        elif current is not None: result[current].append(line)
    return result
def frame(lines):
    total = 0
    for line in lines:
        if re.search(r'\bbl[r]?\s', line): break
        match = re.search(r'\bsub\s+sp,\s*sp,\s*#(0x[0-9a-f]+|\d+)(?:,\s*lsl\s*#(\d+))?', line)
        if match: total += int(match[1], 0) << int(match[2] or 0)
        match = re.search(r'\b(?:stp|str)\s+.*\[sp,\s*#-(0x[0-9a-f]+|\d+)\]!', line)
        if match: total += int(match[1], 0)
    if not total: raise ValueError('unknown/zero stack prologue')
    return total
def audit(assembly):
    blocks = functions(assembly)
    if set(CHAIN) - blocks.keys(): raise ValueError('missing critical path function')
    sizes = {name: frame(blocks[name]) for name in CHAIN}
    for caller, callee in zip(CHAIN, CHAIN[1:]):
        if not any(re.search(r'\bb(?:l)?\s+[^<]+<' + re.escape(callee) + r'>', line) for line in blocks[caller]):
            raise ValueError('critical call edge changed: ' + caller + ' -> ' + callee)
    used, reserve, available = sum(sizes.values()), 1024, 4096
    if used + reserve > available: raise ValueError(f'RPMsg stack budget exceeded: {used}+{reserve}>{available}; {sizes}')
    return dict(path=sizes, known_frames=used, reserve=reserve, pinned_tty_stack=available,
        remaining_after_reserve=available-used-reserve, passed=True,
        limit='Critical integer/string logging path only. Reserve is not a measured worst-case IRQ/leaf bound; pinned M6 default stack assumed, actual TCB must be checked on board.')
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('image', type=Path)
    p.add_argument('toolchain', type=Path); p.add_argument('report', type=Path); a = p.parse_args()
    assembly = subprocess.check_output([str(a.toolchain / 'bin/aarch64-none-elf-objdump'), '-d', str(a.image)], text=True)
    result = audit(assembly); a.report.write_text(json.dumps(result, indent=2) + '\n')
    print('RPMSG STACK BUDGET PASS: ' + str(result))
