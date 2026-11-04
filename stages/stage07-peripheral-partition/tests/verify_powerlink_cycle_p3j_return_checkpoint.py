"""OFFLINE P3j cycle + separately approved Linux-return archive verification.
No board IO, UP lifecycle, frames, module/driver changes or hardware rerun.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from verify_powerlink_cycle_p3j_hw_checkpoint import hardware_evidence
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-return-20261104';OLD=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
sys.path.insert(0,str(STAGE/'tests/board'))
from powerlink_cycle_p3j_checks import SHA,validate_snapshot,match_replies,match_heap
from read_powerlink_cycle_p3j_snapshot import image_symbols
from powerlink_cycle_p3j_tcb_checks import validate_threads
sys.path.pop(0)

def return_evidence():
    print('CHECKING HISTORICAL FAILED RUNNER PHASE (not current board state):',flush=True)
    hardware_evidence()  # Historical original failure is deliberately retained.
    receipt=json.loads((EVIDENCE/'board-input-sha256.json').read_text())
    if (receipt['source_commit']!='659bfb795fea63204978838f65ccde9269bff66e' or receipt['board']!='192.168.2.141' or
            receipt['board_root']!='/root/m7-powerlink-cycle-p3j-20261104/return-linux-20261104' or
            set(receipt['files'])!={'return_powerlink_cycle_p3j_linux.py','powerlink_cycle_p3j_tcb_checks.py','baseline.json'}):
        raise ValueError('not the original three stopped-only return inputs')
    for name,item in receipt['files'].items():
        path=(REPO/item['path']).resolve();path.relative_to(REPO)
        if path.name!=name or path.stat().st_size!=item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('return upload/readback SHA mismatch: '+name)
    baseline=json.loads((EVIDENCE/'baseline.json').read_text())
    old=json.loads((OLD/'board-result.json').read_text());retained=json.loads((OLD/'retained-private.json').read_text())
    before=json.loads(next(x[7:] for x in (OLD/'board-test.log').read_text().splitlines() if x.startswith('BEFORE ')))
    if (baseline['before']!=before or baseline['retained']!=retained or baseline['heap_before']!=old['heap_before'] or
            baseline['completion']!=old['completion'] or baseline['marker']!=(OLD/'ATTEMPTED.txt').read_text() or
            baseline['original_result_sha256']!=hashlib.sha256((OLD/'board-result.json').read_bytes()).hexdigest() or
            baseline['files']!=json.loads((OLD/'board-input-sha256.json').read_text())['files']):
        raise ValueError('return baseline does not match the actual original window')
    result=json.loads((EVIDENCE/'return-result.json').read_text())
    actions=['remove-stopped-client','bind-linux-eth2','linux-eth2-up','release-hold']
    if (result['passed'] is not True or result['cycle_reexecuted'] is not False or result['cpu_stop_issued'] is not False or
            result['attempted_mutations']!=actions or result['completed_mutations']!=actions or result['error'] is not None or
            result['candidate_sha256']!=SHA or result['boot_id']!=old['boot_id']):
        raise ValueError('return failed/incomplete or outside stopped-only scope')
    proof=result['private_stopped']
    for name in ('snapshot','cycle'):
        raw=bytes.fromhex(proof[name+'_hex'])
        if proof[name+'_hex']!=retained[name+'_hex'] or proof[name+'_sha256']!=retained[name+'_sha256'] or hashlib.sha256(raw).hexdigest()!=proof[name+'_sha256']:
            raise ValueError('stopped proof changed before Linux return')
    decoded=validate_snapshot(bytes.fromhex(proof['snapshot_hex']),bytes.fromhex(proof['cycle_hex']),1,1)
    match_replies(decoded,old['completion']['owner'],old['completion']['result'])
    if proof['heap']!=retained['heap'] or proof['heap_comparison']!=match_heap(old['heap_before'],proof['heap']):
        raise ValueError('real FSC proof missing')
    symbols=image_symbols(STAGE/'tests/powerlink-cycle-p3j-20261102/candidates/tl3572-m7-powerlink-p3j-up-b.elf')
    if proof['threads']!=validate_threads([bytes.fromhex(x['raw_hex']) for x in retained['threads_raw']],symbols,decoded['cycle']['owner']):
        raise ValueError('corrected direct/pthread TCB proof missing')
    marker=(EVIDENCE/'LINUX_RETURN_ATTEMPTED.txt').read_text()
    if marker!='candidate='+SHA+'\nboot='+old['boot_id']+'\nscope=stopped-only-linux-return\n':raise ValueError('return permanent marker mismatch')
    log=(EVIDENCE/'board-return.log').read_text()
    if (not log.rstrip().endswith('BOARD_RETURN_EXIT=0') or
            'P3j LINUX RETURN PASS: no cycle/start/stop/reboot; original result and ATTEMPTED preserved' not in log or
            '[plk-cycle] BEGIN' in log):raise ValueError('actual no-rerun return result missing')
    post=(EVIDENCE/'postflight.log').read_text()
    required=(old['boot_id'],'CPU4 PSCI OFF confirmed','CPU5 PSCI OFF confirmed','MainPID=329','NRestarts=0','ActiveState=active',
        '0 loaded units listed.','9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8',
        '3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4')
    if (not post.rstrip().endswith('READ_ONLY_EXIT=0') or any(v not in post for v in required) or
            'up-b-m7-plk-cycle-p3j' in post or 'm7_eth2_power_hold' in post or '/dev/ttyRPMSG' in post):
        raise ValueError('final board state not safely returned')
    for phrase in ('Speed: 100Mb/s','Duplex: Full','Auto-negotiation: on','Link detected: yes'):
        if post.count(phrase)!=2:raise ValueError('Linux two-port100Full restoration missing')
    for name in ('windows.log','linux.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 286 tests' not in text or '\nOK\n' not in text:raise ValueError('286 regressions missing: '+name)
    print('P3j SEPARATE LINUX RETURN PASS: three inputs /same stopped608+1504/FSC/TCB /no cycle or stop /Linux100Full; ORIGINAL FAILURE UNCHANGED',flush=True)

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    for line in (OLD/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('historical source input omitted: '+name)
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and hashlib.sha256((REPO/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('historical source/candidate/evidence changed: '+name)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();return_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve();subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch','0005-mn-request-queue-allocation-errors.patch',
            '0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    print('P3j RETURN FRESH %s PASS: %d SHA /286 Python /1355 upstream+realpatches /cycle+separate safe return; NO BOARD IO' % (commit,count),flush=True)
