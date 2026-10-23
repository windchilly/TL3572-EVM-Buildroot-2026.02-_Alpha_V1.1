"""Exact flat board transport inputs for FUTURE separately authorized P3h run.
Only writes a local artifact manifest; no upload, board, shell or deployment.
"""
import hashlib
import json
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1]; REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-nmt-p3h-runner-20261023'
def runtime_inputs():
    board=STAGE/'tests/board'
    names=('run_powerlink_nmt_p3h_probe.py','powerlink_nmt_p3h_checks.py','read_powerlink_nmt_p3h_snapshot.py',
        'run_powerlink_nmt_probe.py','powerlink_nmt_checks.py','read_powerlink_nmt_snapshot.py',
        'run_powerlink_eth_probe.py','powerlink_eth_checks.py','run_can_direct_pair.py','integrated_mmu_resources.py',
        'eth3_l2_smoke.py','eth2_resources.py','run_integrated_passive.py','can_resource_preflight.py',
        'rs232_resources.py','rs485_resources.py','up-b-m7-plk-nmt-p3h.conf')
    paths=[board/name for name in names]
    paths += [STAGE/'tests/audit_integrated_mmu.py',STAGE/'tests/verify_integrated_elf.py',
        STAGE/'tests/powerlink-nmt-p3h-20261023/candidates/tl3572-m7-powerlink-p3h-up-b.elf',EVIDENCE/'p3h-abi.json']
    return {path.name:dict(path=path.relative_to(REPO).as_posix(),bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}
if __name__=='__main__':
    module=STAGE/'firmware/m7_eth2_power_hold.ko'
    report=dict(prepared_only=True,board_root='/root/m7-powerlink-nmt-p3h-20261023',
        client='up-b-m7-plk-nmt-p3h',kernel='6.12.69-gf1b67c293213',files=runtime_inputs(),
        existing_hold=dict(board_path='/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko',
            path=module.relative_to(REPO).as_posix(),sha256=hashlib.sha256(module.read_bytes()).hexdigest()),
        limit='Preparation only; this manifest is not board upload/physical NMT approval or a readback receipt.')
    (EVIDENCE/'runtime-inputs.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'P3h future runtime inputs: {len(report["files"])} exact files; NO BOARD')
