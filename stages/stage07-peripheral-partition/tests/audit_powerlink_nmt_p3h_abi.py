"""P3h native/AArch64 cache ABI and source-extracted FSC type geometry.
Build-server ONLY; no RTOS execution, board access, stop or deployment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from verify_integrated_elf import symbols_and_data
STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'tests/board'))
from powerlink_nmt_p3h_checks import SHA, CACHE_LAYOUT, PRIVATE_SIZES
from read_powerlink_nmt_p3h_snapshot import image_symbols
sys.path.pop(0)
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'uniproton', 'toolchain', 'report'): p.add_argument(name, type=Path)
    a = p.parse_args(); symbols = image_symbols(a.image)
    header = a.uniproton / 'src/mem/include/prt_mem_external.h'
    source = a.uniproton / 'src/mem/fsc/prt_fscmem.c'
    declaration = re.search(r'struct TagFscMemCtrl \{.*?\n\};', header.read_text(encoding='utf-8'), re.S)
    if not declaration: raise ValueError('FSC private type not found')
    for required in ('size -= OS_FSC_MEM_USED_HEAD_SIZE;', 'g_memTotalSize = (uintptr_t)size;', 'g_memStartAddr = addr;'):
        if required not in source.read_text(encoding='utf-8'): raise ValueError('FSC initialization ABI changed')
    with tempfile.TemporaryDirectory(prefix='tl3572-p3h-abi-') as directory:
        work = Path(directory); probe = work / 'fsc.c'
        # Exact type text from the pinned RTOS header, compiled in isolation.
        # This is NOT a mocked replacement header or a full RTOS binary test.
        probe.write_text('#include <stdint.h>\n' + declaration[0] + '\n'
            'const uint32_t m7_fsc_layout[]={sizeof(struct TagFscMemCtrl),sizeof(uintptr_t)};\n'
            '#ifdef M7_NATIVE_LAYOUT\n#include <stdio.h>\nint main(void){printf("[%u,%u]\\n",m7_fsc_layout[0],m7_fsc_layout[1]);return 0;}\n#endif\n', encoding='utf-8')
        native, cross = {}, {}
        for name, fixture, symbol, expected in (('cache', STAGE/'tests/test_powerlink_nmt_abi.c', 'm7_nmt_layout', CACHE_LAYOUT),
                                               ('fsc', probe, 'm7_fsc_layout', [32,8])):
            flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(STAGE/'source/powerlink/port'),
                '-I', str(STAGE/'source/overlay/uniproton/demos/rk3572_mica/apps/openamp'), str(fixture)]
            subprocess.run(['gcc', *flags, '-DM7_NATIVE_LAYOUT', '-o', str(work/name)], check=True)
            native[name] = json.loads(subprocess.check_output([str(work/name)], text=True))
            obj = work / (name + '.o')
            subprocess.run([str(a.toolchain/'bin/aarch64-none-elf-gcc'), *flags, '-mcpu=cortex-a53',
                '-mgeneral-regs-only', '-mno-outline-atomics', '-c', '-o', str(obj)], check=True)
            cross[name] = list(struct.unpack('<'+str(len(expected))+'I', symbols_and_data(obj)[symbol][2]))
            if native[name] != expected or cross[name] != expected: raise ValueError('actual compiler ABI differs: ' + name)
    report = dict(passed=True, candidate_sha256=SHA, cache_native=native['cache'], cache_aarch64=cross['cache'],
        fsc_native=native['fsc'], fsc_aarch64=cross['fsc'], symbols={name:list(symbols[name][:2]) for name in PRIVATE_SIZES},
        fsc_header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
        fsc_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        rtos_archive_sha256=hashlib.sha256((a.uniproton/'demos/rk3572_mica/libs/libRK3572.a').read_bytes()).hexdigest(),
        limit='Real native/cross header cache layout + exact source-extracted FSC struct; not RTOS execution/heap peak or M6 TCB/exception offset discovery. No firmware change.')
    a.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('P3h NATIVE/AARCH64 CACHE+FSC ABI PASS: ' + json.dumps(report))
