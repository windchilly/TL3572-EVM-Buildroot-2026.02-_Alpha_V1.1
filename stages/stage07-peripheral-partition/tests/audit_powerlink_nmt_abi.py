"""Native + pinned AArch64 compiler header layout, checked against pinned ELF.
No board. This validates cache layout, NOT M6 private TCB/exception ABI or IRQ WC stack.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from verify_integrated_elf import symbols_and_data
STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'tests/board'))
from powerlink_nmt_checks import SHA
sys.path.pop(0)
EXPECTED = [1504, 40, 80, 576, 496, 472, 472, 488, 40, 16, 24, 64, 80, 120, 160, 216, 256, 280, 376, 96, 40, 48, 88]
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'toolchain', 'report'): p.add_argument(name, type=Path)
    a = p.parse_args()
    if hashlib.sha256(a.image.read_bytes()).hexdigest() != SHA: raise ValueError('not pinned P3g candidate')
    symbols = symbols_and_data(a.image)
    if symbols['snapshot'][1] != EXPECTED[0] or 'm7_nmt_probe' not in symbols: raise ValueError('pinned ELF cache mismatch')
    with tempfile.TemporaryDirectory(prefix='tl3572-nmt-abi-') as directory:
        work = Path(directory)
        flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(STAGE / 'source/powerlink/port'),
            '-I', str(STAGE / 'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'), str(STAGE / 'tests/test_powerlink_nmt_abi.c')]
        subprocess.run(['gcc', *flags, '-DM7_NATIVE_LAYOUT', '-o', str(work / 'native')], check=True)
        native = json.loads(subprocess.check_output([str(work / 'native')], text=True))
        subprocess.run([str(a.toolchain / 'bin/aarch64-none-elf-gcc'), *flags, '-mcpu=cortex-a53', '-mgeneral-regs-only',
            '-mno-outline-atomics', '-c', '-o', str(work / 'aarch64.o')], check=True)
        data = symbols_and_data(work / 'aarch64.o')['m7_nmt_layout'][2]
        cross = list(struct.unpack('<' + str(len(EXPECTED)) + 'I', data))
        if native != EXPECTED or cross != EXPECTED: raise ValueError('header ABI differs: ' + str((native, cross)))
    report = dict(candidate_sha256=SHA, passed=True, native=native, aarch64=cross, snapshot_symbol_bytes=symbols['snapshot'][1],
        limit='Header-derived LP64 cache ABI and pinned ELF symbol size only; M6 TCB/exception offsets remain separately pinned, no hardware execution.')
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('P3g NATIVE/AARCH64/PINNED ELF ABI PASS: ' + json.dumps(report))
