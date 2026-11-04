"""Exact FUTURE flat P3j inputs; writes only local manifest, never uploads."""
import hashlib
import json
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1]; REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-runner-20261104'
def runtime_inputs():
    names=('run_powerlink_cycle_p3j_probe.py','powerlink_cycle_p3j_checks.py','read_powerlink_cycle_p3j_snapshot.py',
        'powerlink_nmt_checks.py','run_powerlink_eth_probe.py','powerlink_eth_checks.py','run_can_direct_pair.py',
        'integrated_mmu_resources.py','eth3_l2_smoke.py','eth2_resources.py','run_integrated_passive.py',
        'can_resource_preflight.py','rs232_resources.py','rs485_resources.py','up-b-m7-plk-cycle-p3j.conf')
    paths=[STAGE/'tests/board'/name for name in names]
    paths += [STAGE/'tests/audit_integrated_mmu.py',STAGE/'tests/verify_integrated_elf.py',
        STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf',EVIDENCE/'p3j-abi.json']
    if len({x.name for x in paths}) != len(paths): raise ValueError('flat input collision')
    return {x.name:dict(path=x.relative_to(REPO).as_posix(),bytes=x.stat().st_size,
        sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in paths}
if __name__=='__main__':
    module=STAGE/'firmware/m7_eth2_power_hold.ko'
    log_reader=STAGE/'source/host/up_log_reader.py'
    report=dict(prepared_only=True,board_root='/root/m7-powerlink-cycle-p3j-20261104',client='up-b-m7-plk-cycle-p3j',
        kernel='6.12.69-gf1b67c293213',files=runtime_inputs(),existing_hold=dict(
            board_path='/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko',path=module.relative_to(REPO).as_posix(),
            sha256=hashlib.sha256(module.read_bytes()).hexdigest()),existing_log_reader=dict(
            board_path='/usr/libexec/m7/up_log_reader.py',path=log_reader.relative_to(REPO).as_posix(),
            sha256=hashlib.sha256(log_reader.read_bytes()).hexdigest()),
        limit='Prepared inputs only, NOT upload/readback receipt, hardware approval or execution proof.')
    with (EVIDENCE/'runtime-inputs.json').open('x',encoding='utf-8') as out: json.dump(report,out,indent=2);out.write('\n')
    print('P3j prepared runtime inputs: %d exact files; NO BOARD' % len(report['files']))
