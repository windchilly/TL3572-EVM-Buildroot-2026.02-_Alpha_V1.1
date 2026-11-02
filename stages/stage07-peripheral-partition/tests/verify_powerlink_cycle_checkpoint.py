"""P3i fresh checkout software verification; NO board connection or execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from compare_powerlink_p3a import ARTIFACTS
from verify_powerlink_p3h_hw_checkpoint import verify_evidence
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
def software_evidence():
    evidence=STAGE/'tests/powerlink-cycle-p3i-20261102'
    report=json.loads((evidence/'repro.json').read_text())
    if (report['identical'] is not True or report['hardware_tested'] is not False or report['runtime_images_built'] is not False or
            [x['path'] for x in report['artifacts']]!=list(ARTIFACTS) or len(report['independent_roots'])!=2):
        raise ValueError('fresh software build proof changed')
    log=(evidence/'linux-cycle-final.log').read_text()
    required=('scenario=normal rounds=10 reset=10 off=10 SoC=1280 SoA=2910 ASnd=10 tx_completed_mock=4200',
        'scenario=heap_full rounds=10','heap_peak_model=636816 live=0','scenario=wrong_owner rounds=1',
        'cycle fault dma_fault retained','cycle fault tx_error retained','GAP: stalled TX did not fault automatically',
        'HOST 25ms progress guard','direct SwitchOff rejected busy buffer','stop_failure retained after real cyclic run',
        'timer_release_failure retained after real cyclic run','REMOTE_EXIT=0')
    if any(x not in log for x in required) or log.count('explicit external-sync build rejected')!=2:
        raise ValueError('cycle/safety evidence incomplete')
    for name in ('windows.log','linux-full-repro.log'):
        text=(evidence/name).read_text()
        if 'Ran 208 tests' not in text or not text.rstrip().endswith('EXIT=0'):raise ValueError('208 regression missing: '+name)
    if 'REMOTE_EXIT=134' not in (evidence/'linux-full-build.log').read_text():raise ValueError('original failed stop build log lost')
    print('P3i SOFTWARE evidence PASS: 10+10 native cyclic rounds / ordered stop / 9 scenarios / 2 rejected ext-sync builds / 9 identical artifacts; watchdog GAP retained, NO candidate/board',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    evidence=STAGE/'tests/powerlink-cycle-p3i-20261102';count=0
    for line in (evidence/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('SHA mismatch: '+name)
        count+=1
    software_evidence();verify_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve()
    subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch','0005-mn-request-queue-allocation-errors.patch',
        '0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    canonical=json.loads((STAGE/'tests/powerlink-nmt-p3h-20261023/pdo-memory-canonical.json').read_text())
    if hashlib.sha256((tree/'stack/src/user/pdo/pdou.c').read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=canonical['pdou_source_lf_sha256']:
        raise ValueError('PDO source changed')
    print(f'P3i FRESH CHECKPOINT {commit} PASS: {count} SHA / 208 Python / 1355 files + real0001-0007 / software+historical hardware evidence; NO board',flush=True)
