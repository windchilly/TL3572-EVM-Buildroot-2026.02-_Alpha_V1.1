"""Readonly offline P3h hardware archive check; NO board access or NMT execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from make_powerlink_p3h_runtime_inputs import runtime_inputs
STAGE = Path(__file__).resolve().parents[1]; REPO = STAGE.parents[1]
sys.path.insert(0, str(STAGE/'tests/board'))
from powerlink_nmt_p3h_checks import (SHA, validate_reply, validate_owner, validate_snapshot,
    match_replies, validate_heap_report, match_heap, validate_abi_report)
from read_powerlink_nmt_p3h_snapshot import image_symbols
sys.path.pop(0)

def verify_evidence():
    evidence = STAGE/'tests/powerlink-nmt-p3h-hw-20261023'
    result = json.loads((evidence/'board-result.json').read_text())
    if not (result['passed'] is True and result['cleanup'] is True and result['submitted'] is True and
            result['error'] is None and result['candidate_sha256'] == SHA):
        raise ValueError('hardware window did not complete safely')
    receipt = json.loads((evidence/'board-input-sha256.json').read_text())
    prepared = json.loads((STAGE/'tests/powerlink-nmt-p3h-runner-20261023/runtime-inputs.json').read_text())
    expected = {name:{k:item[k] for k in ('bytes','sha256')} for name,item in runtime_inputs().items()}
    if (receipt['files'] != expected or len(expected) != 21 or receipt['board_root'] != prepared['board_root'] or
            receipt['client'] != prepared['client'] or receipt['source_commit'] != '5830ecf8048e029ef9fae3b3bcc47a5386587c3f'):
        raise ValueError('actual 21-file upload receipt changed')
    symbols = image_symbols(STAGE/'tests/powerlink-nmt-p3h-20261023/candidates/tl3572-m7-powerlink-p3h-up-b.elf')
    for name in ('p3h-abi.json', 'p3h-abi-final.json'):
        validate_abi_report(json.loads((STAGE/'tests/powerlink-nmt-p3h-runner-20261023'/name).read_text()), symbols)
    completion = result['completion']; owner, reply = completion['owner'], completion['result']
    validate_reply('PLK UP2 NMT '+' '.join(k+'='+v for k,v in reply.items())); validate_owner(owner, reply)
    raw = bytes.fromhex((evidence/'private-snapshot.hex').read_text().strip())
    private = result['private_stopped']; decoded = validate_snapshot(raw)
    if hashlib.sha256(raw).hexdigest() != private['snapshot_sha256'] or any(private[k] != v for k,v in decoded.items()):
        raise ValueError('raw stopped cache/report mismatch')
    match_replies(private, owner, reply)
    validate_heap_report(result['heap_before'], 'COLD'); validate_heap_report(private['heap'], 'STOPPED')
    if private['heap_comparison'] != match_heap(result['heap_before'], private['heap']): raise ValueError('heap delta mismatch')
    if (private['heap']['scalars']['g_memPeakUsage'] != 543648 or private['heap']['peak_headroom_bytes'] != 504896 or
            private['ethLease'] or any(private['exception'].values()) or
            sorted((x['name'],x['allocated_stack']) for x in private['threads']) !=
            [('rpmsg_listen_task',4096),('rpmsg_tty_task',4096)]): raise ValueError('real FSC/exception/thread proof changed')
    marker = (evidence/'ATTEMPTED.txt').read_text()
    if marker != 'candidate='+SHA+'\nboot='+result['boot_id']+'\n': raise ValueError('single-attempt marker mismatch')
    for name in ('preflight.log','postflight.log'):
        text = (evidence/name).read_text()
        required = (result['boot_id'],'MainPID=325','NRestarts=0','ActiveState=active',
            'CPU4 PSCI OFF confirmed','CPU5 PSCI OFF confirmed','READ_ONLY_EXIT=0',
            '9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8',
            '3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4')
        if any(x not in text for x in required) or 'Running' in text: raise ValueError('pre/post recovery proof missing')
    log = (evidence/'board-test.log').read_text()
    if (log.count('[plk-nmt-probe] BEGIN') != 1 or 'BOARD_EXIT_CODE=0' not in log or
            'CLEANUP PASS CPU4/5 OFF' not in log): raise ValueError('single-window execution log missing')
    print('OFFLINE hardware evidence PASS: 21 exact uploads, raw 1504 cache, one reset/off, real peak543648/headroom504896, safe Linux return', flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('prepared',type=Path); p.add_argument('--expected-commit',required=True); a = p.parse_args()
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit != a.expected_commit: raise ValueError('unexpected checkout')
    evidence = STAGE/'tests/powerlink-nmt-p3h-hw-20261023'; count = 0
    for line in (evidence/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ',1); path = (REPO/name).resolve(); path.relative_to(REPO)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise ValueError('SHA mismatch: '+name)
        count += 1
    verify_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared = a.prepared.resolve()
    subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree = prepared/'openPOWERLINK_V2-2.7.2'; env = dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch',
        '0005-mn-request-queue-allocation-errors.patch','0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args = ['git','-C',str(tree),'apply','--ignore-space-change']; path = str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']): subprocess.run(args+options+[path],env=env,check=True)
    canonical = json.loads((STAGE/'tests/powerlink-nmt-p3h-20261023/pdo-memory-canonical.json').read_text())
    if hashlib.sha256((tree/'stack/src/user/pdo/pdou.c').read_bytes().replace(b'\r\n',b'\n')).hexdigest() != canonical['pdou_source_lf_sha256']:
        raise ValueError('canonical PDO source mismatch')
    print(f'OFFLINE CHECKPOINT {commit} PASS: {count} SHA / 203 Python / 1355 files + real0001-0007 / hardware evidence; NO board access', flush=True)
