"""Correlate P3d physical readbacks, exact first fault and fixed ELF, no board IO."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'board'))
from powerlink_eth_checks import validate_probe
from read_powerlink_eth_snapshot import decode_exception
from verify_integrated_elf import symbols_and_data

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('evidence', type=Path); a = p.parse_args()
    root = a.evidence
    first = json.loads((root / 'board-dram-snapshot.json').read_text())
    fault = decode_exception(bytes.fromhex(first['symbols']['g_excInfoInternal']['raw_hex']))
    old = root.parent / 'powerlink-eth-p3d-20261010/candidates/tl3572-m7-powerlink-p3d-up-b.elf'
    start, size, code = symbols_and_data(old)['TakeLease']; pc = int(fault['elr'], 16)
    if pc != 0x7c20fe68 or fault['esr'] != '0x2000000' or first['g_ethLease'] or struct.unpack_from('<I', code, pc - start)[0] != 0x88e0fc64:
        raise ValueError('Not the exact original CASAL/pre-MMIO failure')
    recovered = (root / 'restore-pre-mmio-fault.log').read_text()
    if 'CPU5 PSCI OFF confirmed' not in recovered or 'RECOVERY PASS' not in recovered:
        raise ValueError('Missing physical OFF/guarded restore proof')
    report = json.loads((root / 'board-result.json').read_text())
    if not report['passed'] or not report['cleanup'] or report['test_frames'] or len(report['cycles']) != 3:
        raise ValueError('Incomplete hardware result')
    for cycle in report['cycles']:
        validate_probe('PLK UP2 ETH ' + ' '.join(f'{k}={v}' for k, v in cycle['up2'].items()))
        if any(cycle['peer'].get(k) != v for k, v in {'Speed': '100Mb/s', 'Duplex': 'Half', 'Link detected': 'yes'}.items()):
            raise ValueError('Peer mode mismatch')
    image = root / 'candidates/tl3572-m7-powerlink-p3d-armv8a-up-b.elf'
    if hashlib.sha256(image.read_bytes()).hexdigest() != report['candidate_sha256']: raise ValueError('Not tested ELF')
    summary = dict(phase='P3d PHY/MAC100-half + safe stop ONLY', passed=True, cycles=3,
        first_fault=fault, first_fault_opcode='0x88e0fc64 CASAL', first_fault_pre_mmio=True,
        old_candidate_do_not_deploy=True, board_reboot=False, guarded_recovery_cpu_already_off=True,
        fixed_candidate_sha256=report['candidate_sha256'], hardware=report,
        limit='No DMA rings/start or EDRV frames, MN/CN, FCS, realtime or full M7 acceptance')
    (root / 'hardware-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('P3d SUMMARY PASS: exact CASAL first fault, guarded CPU-OFF recovery, fixed PHY/MAC 3 cycles and cleanup')
