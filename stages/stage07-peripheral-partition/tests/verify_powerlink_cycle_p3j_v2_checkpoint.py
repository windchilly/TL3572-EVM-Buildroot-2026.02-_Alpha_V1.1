"""Verify runner-v2 software/actual-byte replay checkpoint; NO BOARD IO."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from make_powerlink_cycle_p3j_v2_runtime_inputs import runtime_inputs
from verify_powerlink_cycle_p3j_return_checkpoint import return_evidence
from replay_powerlink_cycle_p3j_v2 import CASES
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-v2-20261104'
sys.path.insert(0,str(STAGE/'tests/board'))
from read_powerlink_cycle_p3j_v2_snapshot import image_symbols,validate_tcb_abi
from powerlink_cycle_p3j_checks import validate_abi_report,SHA
sys.path.pop(0)

def v2_evidence():
    runtime=json.loads((EVIDENCE/'runtime-inputs.json').read_text())
    if (runtime.get('prepared_only') is not True or runtime['files']!=runtime_inputs() or len(runtime['files'])!=22 or
            runtime['board_root']!='/root/m7-powerlink-cycle-p3j-v2-20261104' or runtime['client']!='up-b-m7-plk-cycle-p3j-v2'):
        raise ValueError('not 22 exact prepared v2 inputs/new profile')
    for name,item in runtime['files'].items():
        path=REPO/item['path']
        if path.name!=name or path.stat().st_size!=item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('prepared input mismatch: '+name)
    for name in ('existing_hold','existing_log_reader'):
        item=runtime[name]
        if hashlib.sha256((REPO/item['path']).read_bytes()).hexdigest()!=item['sha256']:raise ValueError('existing dependency changed')
    cache=json.loads((REPO/runtime['files']['p3j-abi.json']['path']).read_text())
    tcb=json.loads((REPO/runtime['files']['tcb-abi.json']['path']).read_text())
    symbols=image_symbols(REPO/runtime['files']['tl3572-m7-powerlink-p3j-up-b.elf']['path'])
    validate_abi_report(cache,symbols);validate_tcb_abi(tcb,cache)
    replays=[json.loads((EVIDENCE/name).read_text()) for name in ('replay-windows.json','replay-linux.json')]
    for replay in replays:
        if replay.get('software_only') is not True or replay.get('hardware_executed') is not False or set(replay['cases'])!=set(CASES):
            raise ValueError('replay is not the 17 SOFTWARE-only scenarios')
        for name,case in replay['cases'].items():
            result=case['simulated_result'];calls=case['system_calls'];state=case['simulated_final_state']
            commands=[x for x in calls if x[:2]==['diagnostic','PLK cycle-probe']]
            stops=[x for x in calls if x[:2]==['stop','up-b-m7-plk-cycle-p3j-v2']]
            if len(commands)>1 or len(stops)>1:raise ValueError('simulation retried command/stop')
            if name=='abi':
                if result is not None or calls:raise ValueError('ABI failure did not reject before all actions')
                continue
            if name=='normal':
                if (result['passed'] is not True or result['cleanup'] is not True or len(commands)!=1 or len(stops)!=1 or
                        state!={'hold':False,'driver':True,'created':False,'running':False} or
                        len(result['private_stopped']['threads'])!=3 or len(result['private_stopped']['tcb_prefix_hex'])!=17):
                    raise ValueError('new actual-TCB simulation did not close automatically')
            elif name=='ambiguous':
                if result['passed'] is not False or result['cleanup'] is not True or len(commands)!=1:raise ValueError('ambiguous ACK handling changed')
            elif result['cleanup'] or any(x and x[0]=='rmmod' for x in calls):raise ValueError('unknown/fault simulation released resources')
    for name in CASES:
        for field in ('simulated_result','simulated_final_state'):
            if replays[0]['cases'][name][field]!=replays[1]['cases'][name][field]:raise ValueError('Windows/Linux replay semantics differ: '+name)
    for name in ('windows-final-fixed.log','linux-final.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 305 tests' not in text or '\nOK\n' not in text:raise ValueError('305 regression missing')
    log=(EVIDENCE/'linux-final.log').read_text()
    if not log.rstrip().endswith('REMOTE_EXIT=0') or 'P3j native production diagnostic total_budget PASS' not in log:
        raise ValueError('unchanged native production guard regression missing')
    return_evidence()  # Historical actual single cycle + separate return, NOT a new v2 physical run.
    print('P3j runner-v2 SOFTWARE PASS: same candidate '+SHA+' /22 PREPARED inputs /305 Python /17 replay semantics agree /NO BOARD IO',flush=True)

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    old=STAGE/'tests/powerlink-cycle-p3j-return-20261104/SHA256SUMS'
    for line in old.read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('old reproducible input omitted')
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and hashlib.sha256((REPO/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('historical source/candidate/evidence changed: '+name)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();v2_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve();subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch','0005-mn-request-queue-allocation-errors.patch',
            '0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    print('P3j V2 FRESH %s PASS: %d SHA /305 Python /1355 upstream+realpatches /software only; NO BOARD IO' % (commit,count),flush=True)
