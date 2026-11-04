"""Verify P3j software-only runner archive/fresh checkout; never contacts board."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from make_powerlink_cycle_p3j_runtime_inputs import runtime_inputs
from verify_powerlink_cycle_probe_checkpoint import guard_evidence,software_evidence,verify_evidence
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-runner-20261104'
sys.path.insert(0,str(STAGE/'tests/board'))
from powerlink_cycle_p3j_checks import validate_abi_report,SHA,validate_snapshot,decode_cycle
from read_powerlink_cycle_p3j_snapshot import image_symbols
sys.path.pop(0)

def verify_manifest(path, historical_docs=False):
    listed=set()
    for line in path.read_text().splitlines():
        digest,name=line.split('  ',1);target=(REPO/name).resolve();target.relative_to(REPO)
        if name in listed: raise ValueError('duplicate manifest input: '+name)
        rolling_doc=name in ('memory.md','stages/stage07-peripheral-partition/README.md')
        if not (historical_docs and rolling_doc) and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('SHA mismatch: '+name)
        listed.add(name)
    return listed

def runner_evidence():
    listed=verify_manifest(EVIDENCE/'SHA256SUMS')
    # Old manifest remains at its historical commit. Only two rolling indexes
    # are allowed to change here; every historical source/artifact still matches.
    old=verify_manifest(STAGE/'tests/powerlink-cycle-p3j-20261102/SHA256SUMS',historical_docs=True)
    if not old <= listed: raise ValueError('old reproducible inputs omitted')
    image=STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf'
    symbols=image_symbols(image)
    for name in ('p3j-abi.json','p3j-abi-final.json'):
        validate_abi_report(json.loads((EVIDENCE/name).read_text()),symbols)
    if (EVIDENCE/'p3j-abi.json').read_bytes() != (EVIDENCE/'p3j-abi-final.json').read_bytes():
        raise ValueError('native/cross ABI repeat differs')
    runtime=json.loads((EVIDENCE/'runtime-inputs.json').read_text())
    if runtime.get('prepared_only') is not True or runtime['files']!=runtime_inputs() or len(runtime['files'])!=19:
        raise ValueError('prepared runtime inputs changed')
    for kind in ('existing_hold','existing_log_reader'):
        value=runtime[kind]
        if hashlib.sha256((REPO/value['path']).read_bytes()).hexdigest()!=value['sha256']:
            raise ValueError('existing runtime dependency mismatch: '+kind)
    import struct
    for name in ('normal-host.bin','heap-full-host.bin'):
        raw=(EVIDENCE/name).read_bytes();life=decode_cycle(raw)['lifecycle']
        mailbox=bytearray(1504);struct.pack_into('<9I',mailbox,0,1,0,0,1,1,8,0,0,life['final']['owner'])
        mailbox[40:80]=raw[168:208]
        validate_snapshot(mailbox,raw,1,1)  # Synthetic mailbox, actual HOST result only.
    for name in ('windows-final.log','linux-final-fixed.log'):
        text=(EVIDENCE/name).read_text()
        if 'Ran 263 tests' not in text or '\nOK\n' not in text.replace('\r\n','\n'):
            raise ValueError('263 Python regression missing: '+name)
    log=(EVIDENCE/'linux-final-fixed.log').read_text()
    for value in ('P3j HOST actual608B decoder PASS','P3j owner mailbox one-shot/BSS ABI/busy/fault/serialization PASS',
            'P3j native production diagnostic total_budget PASS','REMOTE_EXIT=0'):
        if value not in log: raise ValueError('native/capture regression missing: '+value)
    guard_evidence();software_evidence();verify_evidence()
    print('P3j RUNNER SOFTWARE PASS: %d SHA / 19 prepared inputs / unchanged ELF %s / two native+AArch64 ABI proofs / actual HOST608B; NO BOARD' %
        (len(listed),SHA),flush=True)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit: raise ValueError('unexpected checkout commit')
    count=runner_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve()
    subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch',
            '0005-mn-request-queue-allocation-errors.patch','0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    print('P3j FRESH %s PASS: %d SHA /263 Python /1355 upstream + real0001-0007 /runner /candidate; NO BOARD' % (commit,count),flush=True)
