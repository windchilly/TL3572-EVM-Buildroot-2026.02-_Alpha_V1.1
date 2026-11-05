"""Offline transport-only checkpoint; never runs a peer or opens a board."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4b-20261105'
def sha(data):return hashlib.sha256(data).hexdigest()

def transport_evidence():
    transport=STAGE/'source/powerlink/linux-cn/transport'
    hashes={p.name:sha(p.read_bytes()) for p in sorted(transport.glob('*')) if p.is_file()}
    for mode,machine in (('native','Advanced Micro Devices X86-64'),('aarch64','AArch64')):
        folder=EVIDENCE/(mode+'-final')
        report=json.loads((folder/'build-report.json').read_text())
        repro=json.loads((EVIDENCE/(mode+'-final-repro')/'build-report.json').read_text())
        if (report!=repro or report['source_sha256']!=hashes or report['aarch64']!=(mode=='aarch64') or
                report['board_contacted'] is not False or report['peer_executed'] is not False or report['runtime_ready'] is not False or
                report['mock_network_tests']!=(34 if mode=='native' else 0)):
            raise ValueError('not matching compile-only transport builds: '+mode)
        library=folder/'liboplkcn.a'
        if library.stat().st_size!=report['library']['bytes'] or sha(library.read_bytes())!=report['library']['sha256']:
            raise ValueError('library differs: '+mode)
        machines=set(re.findall(r'Machine:\s+([^\r\n]+)',(folder/'archive-elf-headers.txt').read_text()))
        if machines!={machine}:raise ValueError('archive member architecture changed')
        if not (EVIDENCE/(mode+'-final.log')).read_text().rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('dual build/cmp failed')
    native=(EVIDENCE/'native-final.log').read_text()
    if native.count('CN TRANSPORT PASS ')!=68:raise ValueError('not 34 real-source mock cases twice')
    for phrase in ('unarmed socket=0 close=0 join=0','normal socket=1 close=1 join=1 send=1',
            'join_failure socket=1 close=0 join=1','inflight_timeout socket=1 close=0 join=1',
            'init_close_failure socket=1 close=1 join=0','clock_after_fault socket=1 close=0 join=0',
            'real_thread socket=1 close=1 join=1','deferred socket=1 close=1 join=1 send=0 rx=1 fault=9'):
        if native.count('CN TRANSPORT PASS '+phrase)!=2:raise ValueError('failure/stop proof missing: '+phrase)
    for name in ('windows.log','linux-tests.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 340 tests' not in text or '\nOK\n' not in text:raise ValueError('340 Python regressions missing')
    proof=(EVIDENCE/'linux-tests.log').read_text()
    for name in ('build/build_m7_powerlink_cn_transport.py','source/powerlink/linux-cn/transport/edrv-m7-cn.c',
            'source/powerlink/linux-cn/transport/m7_cn_edrv.h','tests/test_powerlink_cn_transport.c'):
        if sha((STAGE/name).read_bytes())+'  stages/stage07-peripheral-partition/'+name not in proof:
            raise ValueError('actual final build/test source SHA changed')
    if not proof.rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('Linux test command failed')
    old=json.loads((EVIDENCE/'native-fixed/build-report.json').read_text())
    for name,archive in (('edrv-m7-cn.c','first-edrv.c'),('m7_cn_edrv.h','first-header.h')):
        if sha((EVIDENCE/'history'/archive).read_bytes())!=old['source_sha256'][name]:raise ValueError('first transport snapshot changed')
    first=(EVIDENCE/'native-first.log').read_text()
    if not first.rstrip().endswith('REMOTE_EXIT=1') or 'receives==1 && polls==2' not in first:
        raise ValueError('initial mock expectation failure must be retained')
    from verify_powerlink_cn_p4a_checkpoint import software_evidence
    software_evidence()  # Previous prototype/hardware history only, not a new execution.
    print('P4b TRANSPORT SOFTWARE PASS: default unarmed /34 fake-network cases incl real pthread /340 Python /dual native+AArch64 libraries; NOT full CN app or stack teardown acceptance',flush=True)

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or sha(path.read_bytes())!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    for line in (STAGE/'tests/powerlink-cn-p4a-20261105/SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('old reproducible input omitted')
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and sha((REPO/name).read_bytes())!=digest:
            raise ValueError('historical source/firmware/evidence changed: '+name)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();transport_evidence()
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    sys.path.insert(0,str(STAGE/'build'));from prepare_m7_powerlink import prepare
    tree=prepare(a.prepared);env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(tree.parent))
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for options in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+options+[str(patch)],cwd=tree,env=env,check=True)
    print('P4b FRESH %s PASS: %d SHA /340 Python /1355 upstream+Linux patch /transport artifact audit only; NO PEER/BOARD IO' % (commit,count),flush=True)
