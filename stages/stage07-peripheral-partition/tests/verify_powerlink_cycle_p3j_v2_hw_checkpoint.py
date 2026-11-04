"""Offline verification of the one ACTUAL P3j-v2 automatic hardware closure.
Never connects to the board or executes board_window/collect_files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-v2-hw-20261104'
SOURCE='3b07cd341d2874f4e6dba6259ff88e09004e27ae'
sys.path.insert(0,str(STAGE/'tests/board'))
from powerlink_cycle_p3j_checks import SHA,validate_snapshot,match_replies,match_heap
from powerlink_cycle_p3j_tcb_checks import validate_threads
from read_powerlink_cycle_p3j_snapshot import image_symbols
sys.path.pop(0)

def digest(data):return hashlib.sha256(data).hexdigest()

def hardware_evidence(directory=EVIDENCE):
    def read(name):return json.loads((directory/name).read_text())
    runtime=json.loads((STAGE/'tests/powerlink-cycle-p3j-v2-20261104/runtime-inputs.json').read_text())
    receipt=read('board-input-sha256.json');host=read('HOST_EXECUTION_ATTEMPTED.json')
    expected={name:{k:v[k] for k in ('bytes','sha256')} for name,v in runtime['files'].items()}
    if (receipt['board']!='192.168.2.141' or receipt['board_root']!=runtime['board_root'] or
            receipt['client']!=runtime['client'] or receipt['files']!=expected or len(expected)!=22 or
            receipt['source_commit']!=SOURCE or host!=dict(source_commit=SOURCE,board_root=runtime['board_root'],
                candidate_sha256=SHA,scope='new approved single v2 cycle')):
        raise ValueError('not the approved new window/22 exact upload-readback inputs/source')
    result=read('board-result.json');private=result['private_stopped']
    if (result['passed'] is not True or result['cleanup'] is not True or result['submitted'] is not True or
            result['error'] is not None or result['candidate_sha256']!=SHA or private['candidate_sha256']!=SHA):
        raise ValueError('not an actual automatic success')
    report=validate_snapshot(bytes.fromhex(private['snapshot_hex']),bytes.fromhex(private['cycle_hex']),1,1)
    for name in ('snapshot','cycle'):
        if digest(bytes.fromhex(private[name+'_hex']))!=private[name+'_sha256']:raise ValueError('raw hash: '+name)
    for name in ('cache','cycle','lifecycle','mn'):
        if report[name]!=private[name]:raise ValueError('raw decoded metadata changed: '+name)
    if private['ethLease'] or any(private['exception'].values()):raise ValueError('not quiescent/exception-free')
    match_replies(report,result['completion']['owner'],result['completion']['result'])
    heap=match_heap(result['heap_before'],private['heap'])
    if heap!=private['heap_comparison']:raise ValueError('FSC comparison changed')
    image=REPO/runtime['files']['tl3572-m7-powerlink-p3j-up-b.elf']['path']
    records=[bytes.fromhex(x) for x in private['tcb_prefix_hex']]
    if (len(records)!=private['tcb_maximum']+1 or len(records)!=17 or private['tcb_maximum']>=64 or
            not 0x7c200000<=private['tcb_pointer']<=0x7ca00000-len(records)*800):raise ValueError('incomplete TCB proof')
    if validate_threads(records,image_symbols(image),report['cycle']['owner'])!=private['threads']:raise ValueError('actual thread metadata changed')
    before=read('preflight.json');after=read('postflight.json')
    if (before!=after or before['boot']!=result['boot_id'] or before['micad']!=result['micad'] or
            before['can']!={f'can{i}':'DOWN' for i in range(4)} or before['rpmsg'] or before['hold'] or
            before['failed_services'] or before['taint'] & 128):raise ValueError('pre/post baseline drift')
    for name in ('preflight.log','before-upload.log','before-run.log','postflight.log'):
        log=(directory/name).read_text()
        if (not log.rstrip().endswith('READ_ONLY_EXIT=0') or log.count('CPU4 PSCI OFF confirmed')!=2 or
                log.count('CPU5 PSCI OFF confirmed')!=2 or
                json.loads(log.split('SNAPSHOT ',1)[1].rsplit('\nREAD_ONLY_EXIT=',1)[0])!=before):
            raise ValueError('read-only baseline/OFF evidence missing: '+name)
    if (directory/'ATTEMPTED.txt').read_text()!='candidate='+SHA+'\nboot='+result['boot_id']+'\n':raise ValueError('permanent board marker mismatch')
    log=(directory/'board-test.log').read_text()
    for phrase in ('BOARD_EXIT_CODE=0','[plk-cycle] END rc=0 clean=1 stage=9 tx=376',
            'CLEANUP PASS CPU4/5 OFF, Linux full, original clients Offline; management/peripherals unchanged',
            'OVERALL P3j-v2 PASS','P3j-v2 PRIVATE STOPPED PROOF'):
        if phrase not in log:raise ValueError('actual execution evidence missing: '+phrase)
    if (log.count('[plk-cycle] BEGIN one-shot')!=1 or log.count('CPU4 PSCI OFF confirmed')!=5 or
            log.count('CPU5 PSCI OFF confirmed')!=5 or not (directory/'ssh-execution.log').read_text().rstrip().endswith('BOARD_EXIT_CODE=0')):
        raise ValueError('not one cycle with complete independent OFF checks')
    prior=STAGE/'tests/powerlink-cycle-p3j-return-20261104';baseline=json.loads((prior/'baseline.json').read_text())
    paths=dict(baseline['formal_files'])
    paths.update({'/root/m7-powerlink-cycle-p3j-20261104/'+n:v['sha256'] for n,v in baseline['files'].items()})
    paths.update({runtime['board_root']+'/'+n:v['sha256'] for n,v in expected.items()})
    paths.update({runtime['board_root']+'/board-result.json':digest((directory/'board-result.json').read_bytes()),
        runtime['board_root']+'/ATTEMPTED':digest((directory/'ATTEMPTED.txt').read_bytes()),
        '/root/m7-powerlink-cycle-p3j-20261104/ATTEMPTED':digest(baseline['marker'].encode()),
        '/root/m7-powerlink-cycle-p3j-20261104/board-result.json':baseline['original_result_sha256'],
        '/root/m7-powerlink-cycle-p3j-20261104/return-linux-20261104/return-result.json':digest((prior/'return-result.json').read_bytes())})
    files=read('post-file-sha256.json')
    if (files.get('sftp_reads_only') is not True or len(paths)!=52 or set(files['files'])!=set(paths) or
            any(files['files'][n]['sha256']!=v for n,v in paths.items())):raise ValueError('formal/old/new file preservation unproved')
    cycle=report['cycle'];life=report['lifecycle']
    summary=dict(passed=True,automatic_linux_return=True,source_commit=SOURCE,candidate_sha256=SHA,
        tx=life['tx'],timer_irqs=life['timerIrqs'],timer_callbacks=life['timerCallbacks'],rx=life['rx'],
        dropped=life['dropped'],max_late_ticks=cycle['maxLateTicks'],skipped_periods=cycle['skippedPeriods'],
        observed_max_late_us=cycle['maxLateTicks']*1e6/cycle['frequency'],heap=heap,
        limit='Single isolated no-CN diagnostic only; not continuous MN, CN/PDO/SDO, wire capture or worst-case realtime acceptance.')
    print('P3j-v2 ACTUAL automatic closure PASS: 22 exact inputs /one cycle /376 TX /OFF+TCB+FSC /Linux return /52 unchanged files',flush=True)
    return summary

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        d,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or digest(path.read_bytes())!=d:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    for line in (STAGE/'tests/powerlink-cycle-p3j-v2-20261104/SHA256SUMS').read_text().splitlines():
        d,name=line.split('  ',1)
        if name not in listed:raise ValueError('previous reproducible input missing')
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and digest((REPO/name).read_bytes())!=d:
            raise ValueError('historical input changed: '+name)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();print(json.dumps(hardware_evidence(),indent=2))
    from verify_powerlink_cycle_p3j_v2_checkpoint import v2_evidence
    v2_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve();subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for name in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch','0005-mn-request-queue-allocation-errors.patch',
            '0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];patch=str(STAGE/'source/powerlink/port'/name)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[patch],env=env,check=True)
    print('P3j-v2 HW FRESH %s PASS: %d SHA /312 Python /1355 upstream+realpatches /actual automatic closure; NO NEW BOARD IO' % (commit,count),flush=True)
