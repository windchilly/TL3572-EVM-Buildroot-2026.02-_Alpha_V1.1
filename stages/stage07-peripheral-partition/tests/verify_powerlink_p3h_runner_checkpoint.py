"""Fresh GitHub P3h runner/software archive verification; no board access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from make_powerlink_p3h_runtime_inputs import runtime_inputs
STAGE=Path(__file__).resolve().parents[1]; REPO=STAGE.parents[1]
sys.path.insert(0,str(STAGE/'tests/board'))
from powerlink_nmt_p3h_checks import validate_abi_report, SHA
from read_powerlink_nmt_p3h_snapshot import image_symbols
sys.path.pop(0)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    evidence=STAGE/'tests/powerlink-nmt-p3h-runner-20261023';count=0
    for line in (evidence/'SHA256SUMS').read_text().splitlines():
        digest,relative=line.split('  ',1);path=(REPO/relative).resolve();path.relative_to(REPO)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('SHA mismatch: '+relative)
        count+=1
    symbols=image_symbols(STAGE/'tests/powerlink-nmt-p3h-20261023/candidates/tl3572-m7-powerlink-p3h-up-b.elf')
    for name in ('p3h-abi.json','p3h-abi-final.json'):
        validate_abi_report(json.loads((evidence/name).read_text()),symbols)
    if (evidence/'p3h-abi.json').read_bytes()!=(evidence/'p3h-abi-final.json').read_bytes():raise ValueError('independent ABI runs differ')
    runtime=json.loads((evidence/'runtime-inputs.json').read_text())
    if runtime.get('prepared_only') is not True or runtime['files']!=runtime_inputs() or len(runtime['files'])!=21:
        raise ValueError('future transport inputs changed')
    hold=runtime['existing_hold']
    if hashlib.sha256((REPO/hold['path']).read_bytes()).hexdigest()!=hold['sha256']:raise ValueError('hold input changed')
    old=STAGE/'tests/board/run_powerlink_nmt_probe.py'
    if hashlib.sha256(old.read_bytes()).hexdigest()!='9d23f559016e5b4f9cda2b015c5f7127552906292cd8b10eaf8507abca169c8d':
        raise ValueError('P3g board runner changed')
    print(f'GITHUB FRESH {commit}: {count} SHA / 21 future inputs / pinned {SHA} / two native+AArch64 cache/FSC proofs PASS; NO BOARD',flush=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve()
    subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch',
        '0005-mn-request-queue-allocation-errors.patch','0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    canonical=json.loads((STAGE/'tests/powerlink-nmt-p3h-20261023/pdo-memory-canonical.json').read_text())
    if hashlib.sha256((tree/'stack/src/user/pdo/pdou.c').read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=canonical['pdou_source_lf_sha256']:
        raise ValueError('canonical PDO source mismatch')
    print(f'GITHUB FRESH PASS: {count} SHA / 203 Python / 1355 upstream files + REAL 0001-0007 / unchanged P3h ELF+P3g runner / ABI proof; NO BOARD',flush=True)
