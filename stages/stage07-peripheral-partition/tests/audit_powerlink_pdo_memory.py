"""Compile pinned private PDO geometry; compare with retained READ-ONLY heap evidence.
No firmware link, board access, heap traversal, cleanup or recovery.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from verify_integrated_elf import symbols_and_data
STAGE = Path(__file__).resolve().parents[1]
EXPECTED = [16, 254, 254, 16, 576, 512, 512, 516, 536, 544]
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('upstream', 'toolchain', 'allocator_log', 'report'): p.add_argument(name, type=Path)
    a = p.parse_args()
    scalar, end = json.JSONDecoder().raw_decode(a.allocator_log.read_text())
    if a.allocator_log.read_text()[end:].strip() != 'EXIT=0': raise ValueError('diagnostic did not complete')
    compiler = a.toolchain / 'bin/aarch64-none-elf-gcc'
    with tempfile.TemporaryDirectory(prefix='tl3572-pdo-geometry-') as directory:
        output = Path(directory) / 'pdo.o'
        subprocess.run([str(compiler), '-std=c11', '-O2', '-DOPLK_TARGET_UNIPROTON', '-DCONFIG_MN',
            '-include', 'common/oplkinc.h', '-I', str(STAGE / 'source/powerlink/port'),
            '-I', str(a.upstream / 'stack/include'), '-I', str(a.upstream / 'stack/src'),
            '-I', str(a.upstream / 'contrib'), '-mcpu=cortex-a53', '-mgeneral-regs-only',
            '-mno-outline-atomics', '-c', str(STAGE / 'tests/test_powerlink_pdo_memory.c'), '-o', str(output)], check=True)
        geometry = list(struct.unpack('<10I', symbols_and_data(output)['m7_pdo_geometry'][2]))
    if geometry != EXPECTED: raise ValueError('PDO layout changed: ' + str(geometry))
    total, used = (scalar['scalars'][name] for name in ('g_memTotalSize', 'g_memUsage'))
    counts = int(scalar['pdou_tail_qwords'][0], 16)
    rx, tx = counts & 0xffffffff, counts >> 32
    request = geometry[0] * tx * geometry[2]
    free = total - used
    if (rx, tx) != (40, 40) or scalar['pdou_tail_qwords'][4] != '0x0' or request <= free:
        raise ValueError('not the documented failed TX PDO allocation')
    report = dict(candidate_sha256=scalar['candidate_sha256'], geometry=geometry,
        compiler=subprocess.check_output([str(compiler), '--version'], text=True).splitlines()[0],
        pdou_source_sha256=hashlib.sha256((a.upstream / 'stack/src/user/pdo/pdou.c').read_bytes()).hexdigest(),
        pdou_source_lf_sha256=hashlib.sha256((a.upstream / 'stack/src/user/pdo/pdou.c').read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        heap_total_bytes=total, heap_used_bytes=used, heap_free_bytes=free,
        rx_channels=rx, tx_channels=tx, mapping_object_bytes=geometry[0], tx_objects_per_channel=geometry[2],
        tx_mapping_request_bytes=request, minimum_shortfall_bytes=request-free,
        tx_mapping_pointer=scalar['pdou_tail_qwords'][4],
        conclusion='TX PDO mapping request exceeds total remaining RTOS FSC heap, even before allocation overhead.',
        limit='Point-in-time metadata plus source geometry; original error was overwritten, not a heap/stack peak or stop proof. Native host malloc did not model shared MICA/RTOS heap usage.')
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
