"""P3j actual bounded cycle / retained cleanup failure, OFFLINE ONLY.
Never loads, sends, retries, stops or changes the board. Original failure stays.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from verify_powerlink_cycle_probe_checkpoint import guard_evidence
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
sys.path.insert(0,str(STAGE/'tests/board'))
from powerlink_cycle_p3j_checks import SHA,validate_snapshot,match_replies,match_heap
from read_powerlink_cycle_p3j_snapshot import image_symbols
from powerlink_cycle_p3j_tcb_checks import TCB_LAYOUT,validate_threads
sys.path.pop(0)

def hardware_evidence():
    prepared=STAGE/'tests/powerlink-cycle-p3j-runner-20261104'
    inputs=json.loads((prepared/'runtime-inputs.json').read_text())
    receipt=json.loads((EVIDENCE/'board-input-sha256.json').read_text())
    expected={name:{k:v for k,v in value.items() if k in ('bytes','sha256')} for name,value in inputs['files'].items()}
    if (len(expected)!=19 or receipt['files']!=expected or receipt['board_root']!=inputs['board_root'] or
            receipt['client']!=inputs['client'] or receipt['board']!='192.168.2.141' or
            receipt['source_commit']!='2d36c3a0c9188cb1ccbdfe2430a607ff55364cfc'):
        raise ValueError('not original 19 upload/readback inputs and execution source')
    image=STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf'
    symbols=image_symbols(image)
    result=json.loads((EVIDENCE/'board-result.json').read_text())
    if (result['passed'] is not False or result['cleanup'] is not False or result['submitted'] is not True or
            result['private_stopped'] is not None or result['candidate_sha256']!=SHA or
            result['error']!='actual RPMsg/PLKowner stacks changed/missing'):
        raise ValueError('original cleanup failure must not be rewritten as PASS')
    retained=json.loads((EVIDENCE/'retained-private.json').read_text())
    raw=bytes.fromhex((EVIDENCE/'private-snapshot.hex').read_text().strip())
    cycle=bytes.fromhex((EVIDENCE/'private-cycle.hex').read_text().strip())
    report=validate_snapshot(raw,cycle,1,1)
    for name,value in (('snapshot',raw),('cycle',cycle)):
        if value.hex()!=retained[name+'_hex'] or hashlib.sha256(value).hexdigest()!=retained[name+'_sha256']:
            raise ValueError('actual private evidence changed: '+name)
    match_replies(report,result['completion']['owner'],result['completion']['result'])
    if retained['ethLease'] or any(retained['exception'].values()):raise ValueError('not quiet retained private state')
    comparison=match_heap(result['heap_before'],retained['heap'])
    records=[bytes.fromhex(v['raw_hex']) for v in retained['threads_raw']]
    if len(records)!=retained['tcb_maximum']+1:raise ValueError('incomplete TCB prefixes')
    threads=validate_threads(records,symbols,report['cycle']['owner'])
    proof=json.loads((EVIDENCE/'tcb-abi.json').read_text())
    if ((EVIDENCE/'tcb-abi.json').read_bytes()!=(EVIDENCE/'tcb-abi-final.json').read_bytes() or
            proof.get('passed') is not True or proof['candidate_sha256']!=SHA or
            proof['native']!=TCB_LAYOUT or proof['aarch64']!=TCB_LAYOUT):raise ValueError('TCB actual compiler proof missing')
    original_abi=json.loads((prepared/'p3j-abi.json').read_text())
    if proof['source_sha256']['demos/rk3572_mica/libs/libRK3572.a']!=original_abi['rtos_archive_sha256']:
        raise ValueError('TCB proof used a different RTOS archive')
    marker=(EVIDENCE/'ATTEMPTED.txt').read_text()
    if marker!='candidate='+SHA+'\nboot='+result['boot_id']+'\n':raise ValueError('permanent one-shot marker mismatch')
    log=(EVIDENCE/'board-test.log').read_text()
    for phrase in ('BOARD_EXIT_CODE=1','[plk-cycle] END rc=0 clean=1 stage=9 tx=376','reached=0x2fd',
            'CLEANUP STOPPED:','actual RPMsg/PLKowner stacks changed/missing','CPU5 PSCI OFF confirmed'):
        if phrase not in log:raise ValueError('actual original log missing: '+phrase)
    if log.count('[plk-cycle] BEGIN one-shot')!=1:raise ValueError('not exactly one cycle execution')
    readonly=(EVIDENCE/'retained-readonly.log').read_text()
    if (readonly.count('CPU4 PSCI OFF confirmed')!=2 or readonly.count('CPU5 PSCI OFF confirmed')!=2 or
            not readonly.rstrip().endswith('READ_ONLY_EXIT=0')):raise ValueError('independent before/after OFF evidence missing')
    for name in ('windows.log','linux-final.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 273 tests' not in text or '\nOK\n' not in text:raise ValueError('273 regression missing: '+name)
    if not (EVIDENCE/'linux-final.log').read_text().rstrip().endswith('REMOTE_EXIT=0'):
        raise ValueError('Linux full command failed')
    summary=dict(cycle_completed=True,original_overall_passed=False,cleanup_restored=False,retained=True,
        candidate_sha256=SHA,boot_id=result['boot_id'],threads=threads,heap=comparison,
        tx=report['lifecycle']['tx'],timer_irqs=report['lifecycle']['timerIrqs'],
        timer_callbacks=report['lifecycle']['timerCallbacks'],max_late_ticks=report['cycle']['maxLateTicks'],
        skipped_periods=report['cycle']['skippedPeriods'],
        limit='Actual isolated no-CN bounded cycle only; cleanup pending separate authority, not realtime/CN/PDO/SDO acceptance.')
    print('P3j ACTUAL bounded cycle/19 inputs/608+1504/real FSC/TCB PASS; ORIGINAL CLEANUP FAILED and remains RETAINED',flush=True)
    return summary

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);target=(REPO/name).resolve();target.relative_to(REPO)
        if name in listed or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    old=STAGE/'tests/powerlink-cycle-p3j-runner-20261104/SHA256SUMS'
    for line in old.read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('old reproducible input omitted: '+name)
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and hashlib.sha256((REPO/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('pinned old source/candidate/evidence changed: '+name)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected source checkout')
    count=verify_manifest();hardware_evidence();guard_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve()
    subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch','0005-mn-request-queue-allocation-errors.patch',
            '0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    print('P3j HW ARCHIVE FRESH %s PASS: %d SHA /273 Python /1355 upstream+realpatches /cycle PASS but cleanup RETAINED; NO BOARD IO' % (commit,count),flush=True)
