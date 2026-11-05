"""Offline P4a source/artifact reproducibility verification; no peer/board IO."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4a-20261105'
sys.path.insert(0,str(STAGE/'build'))
from inspect_m7_powerlink_cdc import baseline_report
sys.path.pop(0)
def sha(data):return hashlib.sha256(data).hexdigest()

def software_evidence():
    baseline=json.loads((EVIDENCE/'baseline.json').read_text())
    if baseline!=baseline_report() or (EVIDENCE/'baseline.json').read_bytes()!=(EVIDENCE/'baseline-linux.json').read_bytes():
        raise ValueError('pinned no-CN source baseline/Windows-Linux report differs')
    proof=(EVIDENCE/'build-source-check.log').read_text()
    for name in ('build/build_m7_powerlink_linux_cn.py','build/prepare_m7_powerlink.py',
            'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'):
        line=sha((STAGE/name).read_bytes())+'  stages/stage07-peripheral-partition/'+name
        if line not in proof:raise ValueError('actual final build source differs: '+name)
    if not proof.rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('build source check failed')
    for mode,machine in (('native',62),('aarch64',183)):
        folder=EVIDENCE/(mode+'-final');report=json.loads((folder/'build-report.json').read_text())
        repro=json.loads((EVIDENCE/(mode+'-final-repro')/'build-report.json').read_text())
        if (report!=repro or report['role']!='CN' or report['driver']!='edrv-rawsock_linux.c' or
                report['software_only'] is not True or report['executed'] is not False or report['board_contacted'] is not False or
                report['deterministic_archives'] is not True or report['aarch64']!=(mode=='aarch64')):
            raise ValueError('not two matching compile-only CN builds: '+mode)
        patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
        if sha(patch.read_bytes())!=report['linux_cn_patch_sha256']:raise ValueError('Linux-only patch changed')
        for name,item in report['artifacts'].items():
            path=folder/Path(name).name
            if path.stat().st_size!=item['bytes'] or sha(path.read_bytes())!=item['sha256']:raise ValueError('artifact SHA: '+str(path))
        elf=(folder/'demo_cn_console').read_bytes()
        if elf[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',elf,18)[0]!=machine:raise ValueError('ELF architecture mismatch')
        if 'pcap' in (folder/'elf-dynamic.txt').read_text().lower():raise ValueError('unexpected pcap runtime dependency')
        if not (EVIDENCE/(mode+'-final.log')).read_text().rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('dual fresh build/cmp failed')
    for name in ('windows.log','linux-tests.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 330 tests' not in text or '\nOK\n' not in text:raise ValueError('330 regression missing')
    if not (EVIDENCE/'linux-tests.log').read_text().rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('Linux audit/regression command failed')
    # Retain the non-deterministic first archive comparison, never rewrite it.
    if not (EVIDENCE/'native-repro.log').read_text().rstrip().endswith('REMOTE_EXIT=1'):raise ValueError('initial archive mismatch evidence missing')
    plan=json.loads((STAGE/'config/powerlink-linux-cn-peer.plan.json').read_text())
    if plan['physical_cn_available'] is not False or plan['peer_executed'] is not False or plan['runtime_ready'] is not False:
        raise ValueError('plan must not claim deployment or acceptance')
    from verify_powerlink_cycle_p3j_v2_hw_checkpoint import hardware_evidence
    hardware_evidence()  # Historical 11/04 hardware proof, not a new board run.
    print('P4a SOFTWARE PASS: raw-socket CN native+AArch64 /two fresh builds each /330 tests /same no-CN P3j /NO PEER OR BOARD EXECUTION',flush=True)

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or sha(path.read_bytes())!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    for line in (STAGE/'tests/powerlink-cycle-p3j-v2-hw-20261104/SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('old reproducible input omitted')
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and sha((REPO/name).read_bytes())!=digest:
            raise ValueError('old source/firmware/evidence changed: '+name)
    return len(listed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();software_evidence()
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    sys.path.insert(0,str(STAGE/'build'))
    from prepare_m7_powerlink import prepare
    tree=prepare(a.prepared);env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(tree.parent))
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for options in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+options+[str(patch)],cwd=tree,env=env,check=True)
    print('P4a FRESH %s PASS: %d SHA /330 Python /1355 upstream+Linux patch /artifact audit, NOT peer execution or rebuild' % (commit,count),flush=True)
