"""Offline P4c evidence/source audit. No C/peer execution, network or board IO."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4c-20261105'
sys.path.insert(0,str(STAGE/'build'))
from build_m7_powerlink_cn_lifecycle import CASES,WORKER_CASES
from apply_m7_powerlink_cn_lifecycle import apply
from prepare_m7_powerlink import prepare

def sha(data):return hashlib.sha256(data).hexdigest()

def lifecycle_evidence():
    generated=None
    for mode,machine in (('native','Advanced Micro Devices X86-64'),('aarch64','AArch64')):
        folder=EVIDENCE/(mode+'-final');report=json.loads((folder/'build-report.json').read_text())
        repro=json.loads((EVIDENCE/(mode+'-final-repro')/'build-report.json').read_text())
        if report!=repro or report['aarch64']!=(mode=='aarch64'):
            raise ValueError('dual fresh builds differ: '+mode)
        for name,digest in report['input_sha256'].items():
            if sha((STAGE/name).read_bytes())!=digest:raise ValueError('actual compiled source differs: '+name)
        for key in ('board_contacted','peer_executed','runtime_ready'):
            if report[key] is not False:raise ValueError('software-only boundary changed')
        if (report['mock_lifecycle_tests']!=(len(CASES) if mode=='native' else 0) or
            report['mock_io_real_worker_tests']!=(len(WORKER_CASES) if mode=='native' else 0)):
            raise ValueError('not 26 control +4 actual worker scenarios')
        library=folder/'liboplkcn.a'
        if library.stat().st_size!=report['library']['bytes'] or sha(library.read_bytes())!=report['library']['sha256']:
            raise ValueError('library digest differs: '+mode)
        machines=set(re.findall(r'Machine:\s+([^\r\n]+)',(folder/'archive-elf-headers.txt').read_text()))
        if machines!={machine}:raise ValueError('archive member architecture changed')
        if generated is not None and generated!=report['generated_sha256']:raise ValueError('architecture source drift')
        generated=report['generated_sha256']
        if not (EVIDENCE/(mode+'-final.log')).read_text().rstrip().endswith('REMOTE_EXIT=0'):
            raise ValueError('build/cmp failed')
    native=(EVIDENCE/'native-final.log').read_text()
    for kind,cases in (('lifecycle',CASES),('workers',WORKER_CASES)):
        for case in cases:
            if len(re.findall(r'^PASS '+kind+' '+case+r' ',native,re.M))!=2:
                raise ValueError('case not independently passed twice: '+kind+'/'+case)
    for phrase in ('partial_init created=2 joined=2 stop=1 releases=0 env=0',
                   'join_hres created=4 joined=4 stop=1 releases=0 env=0',
                   'transport_unclosed created=4 joined=4 stop=1 releases=0 env=0',
                   'user_release_failure created=4 joined=4 stop=1 releases=1 env=0',
                   'kernel_release_failure created=4 joined=4 stop=1 releases=10 env=0',
                   'kernel_retval_failure created=4 joined=4 stop=1 releases=9 env=0'):
        if native.count('PASS lifecycle '+phrase)!=2:raise ValueError('retention proof missing: '+phrase)
    for phrase in ('normal entered=4 completed=4 joins=4 freed=13 fault=0',
                   'sem_close_failure entered=4 completed=4 joins=4 freed=3 fault=5',
                   'timer_delete_failure entered=4 completed=4 joins=4 freed=0 fault=5',
                   'queue_exit_failure entered=4 completed=4 joins=4 freed=0 fault=8'):
        if native.count('PASS workers '+phrase)!=2:raise ValueError('actual worker/release proof missing: '+phrase)
    for name in ('windows-final.log','linux-tests.log'):
        proof=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 352 tests' not in proof or '\nOK\n' not in proof:raise ValueError('352 Python checks missing: '+name)
        if not proof.rstrip().endswith('EXIT=0'):raise ValueError('test command failed: '+name)
    linux=(EVIDENCE/'linux-tests.log').read_text()
    inputs=json.loads((EVIDENCE/'native-final/build-report.json').read_text())['input_sha256']
    for name,digest in inputs.items():
        if digest+'  stages/stage07-peripheral-partition/'+name not in linux:
            raise ValueError('Linux actual-source SHA not recorded: '+name)
    # Diagnostic failures stay failures; no source or hardware failures are relabeled.
    for name,reason in (('native-first.log','unexpected pinned Linux CN input'),
                        ('native-third.log','-Werror=misleading-indentation'),
                        ('windows.log',"'mock-lifecycle-tests' not found")):
        proof=(EVIDENCE/name).read_text()
        if reason not in proof or not proof.rstrip().endswith('EXIT=1'):
            raise ValueError('original diagnostic failure omitted: '+name)
    from verify_powerlink_cn_p4b_checkpoint import transport_evidence
    transport_evidence()  # Historical evidence/source audit only, no old/new runs.
    print('P4c SOFTWARE PASS: 26 production-control +4 actual-four-worker mock-IO cases twice /352 Python /dual libraries; NOT runnable CN or all-module integration',flush=True)
    return generated

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or sha(path.read_bytes())!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    old=STAGE/'tests/powerlink-cn-p4b-20261105'
    for line in (old/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('old reproducible input omitted')
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and sha((REPO/name).read_bytes())!=digest:
            raise ValueError('historical source/firmware/evidence changed: '+name)
    return len(listed)

def source_check(destination,expected):
    tree=prepare(destination);env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(tree.parent))
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for options in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+options+[str(patch)],cwd=tree,env=env,check=True)
    if apply(tree)!=expected:raise ValueError('fresh generated lifecycle sources differ from actual dual build inputs')
    print('P4c SOURCE PASS: pinned 1355 files +Linux patch +9 locked transformations; generated SHA matches native/AArch64',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();generated=lifecycle_evidence()
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    source_check(a.prepared,generated)
    print('P4c FRESH %s PASS: %d SHA /352 Python /pinned source+overlay proof; NO C/PEER/BOARD IO' % (commit,count),flush=True)
