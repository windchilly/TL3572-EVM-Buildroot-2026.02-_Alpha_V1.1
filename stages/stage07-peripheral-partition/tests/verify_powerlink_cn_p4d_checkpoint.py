"""Offline P4d source/evidence audit: never runs C/CN or contacts a board."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4d-20261105'
sys.path.insert(0,str(STAGE/'build'))
from build_m7_powerlink_cn_private import CONTROL_CASES,PRIVATE_CASES,STACK_CASES,FORBIDDEN
from apply_m7_powerlink_cn_private import apply
from prepare_m7_powerlink import prepare
def sha(data):return hashlib.sha256(data).hexdigest()

def private_evidence():
    generated=None;inputs=None
    for mode,machine in (('native','Advanced Micro Devices X86-64'),('aarch64','AArch64')):
        folder=EVIDENCE/(mode+'-final');report=json.loads((folder/'build-report.json').read_text())
        repro=json.loads((EVIDENCE/(mode+'-final-repro')/'build-report.json').read_text())
        if report!=repro or report['aarch64']!=(mode=='aarch64'):raise ValueError('dual builds differ: '+mode)
        for name,digest in report['input_sha256'].items():
            if sha((STAGE/name).read_bytes())!=digest:raise ValueError('compiled input drift: '+name)
        for name in ('board_contacted','peer_executed','runtime_ready'):
            if report[name] is not False:raise ValueError('software-only boundary drift')
        for field,cases in (('mock_control_tests',CONTROL_CASES),('private_tests',PRIVATE_CASES),('mock_stack_tests',STACK_CASES)):
            if report[field]!=(len(cases) if mode=='native' else 0):raise ValueError('actual C case counts differ')
        library=folder/'liboplkcn.a'
        if sha(library.read_bytes())!=report['library']['sha256'] or library.stat().st_size!=report['library']['bytes']:
            raise ValueError('library digest differs')
        if set(re.findall(r'Machine:\s+([^\r\n]+)',(folder/'archive-elf-headers.txt').read_text()))!={machine}:
            raise ValueError('archive member architecture differs')
        if report['forbidden_undefined_symbols']!=list(FORBIDDEN):raise ValueError('forbidden symbol policy differs')
        undefined={line.split()[-1] for line in (folder/'undefined-symbols.txt').read_text().splitlines() if line.strip()}
        if undefined.intersection(FORBIDDEN):raise ValueError('named IPC or POSIX signal timer still referenced')
        if generated is not None and (generated!=report['generated_sha256'] or inputs!=report['input_sha256']):raise ValueError('native/cross source drift')
        generated=report['generated_sha256'];inputs=report['input_sha256']
        if not (EVIDENCE/(mode+'-final.log')).read_text().rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('build/cmp failed')
    native=(EVIDENCE/'native-final.log').read_text()
    for kind,cases in (('lifecycle',CONTROL_CASES),('private',PRIVATE_CASES),('stack',STACK_CASES)):
        for case in cases:
            if len(re.findall(r'^PASS '+kind+' '+case+r' ',native,re.M))!=2:raise ValueError('not independently passed twice: '+kind+'/'+case)
    for phrase in ('normal creates=4 joins=4 stops=1 callbacks=2 semDestroy=3 condDestroy=2 buffers=0',
                   'partial_edrv creates=2 joins=2 stops=1 callbacks=0 semDestroy=0 condDestroy=0 buffers=3',
                   'partial_thread creates=4 joins=3 stops=1 callbacks=0 semDestroy=0 condDestroy=0 buffers=6',
                   'pdo_mutex_failure creates=4 joins=4 stops=1 callbacks=0 semDestroy=1 condDestroy=0 buffers=6'):
        if native.count('PASS stack '+phrase)!=2:raise ValueError('actual passive stack/retention proof missing')
    if native.count('PASS private queue_child ')!=2:raise ValueError('separate-process isolation helper missing')
    for name in ('windows-final.log','linux-tests.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 368 tests' not in text or '\nOK\n' not in text or not text.rstrip().endswith('EXIT=0'):
            raise ValueError('368 regressions missing: '+name)
    text=(EVIDENCE/'linux-tests.log').read_text()
    for name,digest in inputs.items():
        if digest+'  stages/stage07-peripheral-partition/'+name not in text:raise ValueError('actual Linux input SHA missing: '+name)
    for name,reason in (('native-first.log','common/event.h: No such file'),
                        ('native-third.log',"implicit declaration of function 'nmtk_getNmtState'"),
                        ('native-fifth.log','STACK COUNTERS creates=4 joins=4 stops=1 semDestroy=3 condDestroy=2')):
        text=(EVIDENCE/name).read_text()
        if reason not in text or not text.rstrip().endswith('EXIT=1'):raise ValueError('diagnostic failure overwritten/omitted')
    from verify_powerlink_cn_p4c_checkpoint import lifecycle_evidence
    lifecycle_evidence() # Historical artifacts/source audit, not rerunning older code.
    print('P4d SOFTWARE PASS: 26 control +25 private +4 actual passive-stack cases twice /368 Python /dual libraries /no named IPC or signal timer imports; NOT runnable CN/MN interoperability',flush=True)
    return generated

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or sha(path.read_bytes())!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    old=STAGE/'tests/powerlink-cn-p4c-20261105'
    for line in (old/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('old reproducible input omitted')
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and sha((REPO/name).read_bytes())!=digest:
            raise ValueError('historical source/artifact/evidence changed: '+name)
    return len(listed)

def source_check(destination,expected):
    tree=prepare(destination);env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(tree.parent))
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for options in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+options+[str(patch)],cwd=tree,env=env,check=True)
    if apply(tree)!=expected:raise ValueError('fresh source/private-overlay SHA differs from dual builds')
    print('P4d SOURCE PASS: 1355 pinned files +immutable P4c baseline +private overlay; exact generated SHA',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();generated=private_evidence()
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    source_check(a.prepared,generated)
    print('P4d FRESH %s PASS: %d SHA /368 Python /pinned source+private overlay; NO C/CN/BOARD IO' % (commit,count),flush=True)
