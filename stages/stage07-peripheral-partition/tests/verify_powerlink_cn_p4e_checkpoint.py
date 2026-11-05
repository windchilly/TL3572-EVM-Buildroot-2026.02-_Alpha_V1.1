"""Offline P4e evidence/source audit. No C/CN execution or board IO."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4e-20261105'
sys.path.insert(0,str(STAGE/'build'))
from build_m7_powerlink_cn_startup import CONTROL_CASES,PRIVATE_CASES,STARTUP_CASES,FORBIDDEN
from apply_m7_powerlink_cn_startup import apply
from prepare_m7_powerlink import prepare
def sha(data):return hashlib.sha256(data).hexdigest()

def startup_evidence():
    generated=None;inputs=None
    for mode,machine in (('native','Advanced Micro Devices X86-64'),('aarch64','AArch64')):
        folder=EVIDENCE/(mode+'-final');report=json.loads((folder/'build-report.json').read_text())
        repro=json.loads((EVIDENCE/(mode+'-final-repro')/'build-report.json').read_text())
        if report!=repro or report['aarch64']!=(mode=='aarch64'):raise ValueError('dual reports differ: '+mode)
        for name,digest in report['input_sha256'].items():
            if sha((STAGE/name).read_bytes())!=digest:raise ValueError('compiled input drift: '+name)
        for name in ('board_contacted','peer_executed','runtime_ready'):
            if report[name] is not False:raise ValueError('software-only boundary drift')
        for name,cases in (('mock_control_tests',CONTROL_CASES),('private_tests',PRIVATE_CASES),('mock_stack_tests',STARTUP_CASES)):
            if report[name]!=(len(cases) if mode=='native' else 0):raise ValueError('C case counts differ')
        library=folder/'liboplkcn.a'
        if sha(library.read_bytes())!=report['library']['sha256'] or library.stat().st_size!=report['library']['bytes']:
            raise ValueError('library SHA/size differs')
        machines=set(re.findall(r'Machine:\s+([^\r\n]+)',(folder/'archive-elf-headers.txt').read_text()))
        if machines!={machine}:raise ValueError('member architecture differs')
        if report['forbidden_undefined_symbols']!=list(FORBIDDEN):raise ValueError('symbol policy differs')
        undefined={line.split()[-1] for line in (folder/'undefined-symbols.txt').read_text().splitlines() if line.strip()}
        if undefined.intersection(FORBIDDEN):raise ValueError('named IPC or POSIX timer reference')
        if generated is not None and (generated!=report['generated_sha256'] or inputs!=report['input_sha256']):
            raise ValueError('native/cross source drift')
        generated=report['generated_sha256'];inputs=report['input_sha256']
        if not (EVIDENCE/(mode+'-final.log')).read_text().rstrip().endswith('REMOTE_EXIT=0'):raise ValueError('build/cmp failed')
    native=(EVIDENCE/'native-final.log').read_text()
    for kind,cases in (('lifecycle',CONTROL_CASES),('private',PRIVATE_CASES),('startup',STARTUP_CASES)):
        for case in cases:
            if len(re.findall(r'^PASS '+kind+' '+case+r' ',native,re.M))!=2:raise ValueError('C case not passed twice: '+kind+'/'+case)
    if native.count('PASS private queue_child ')!=2:raise ValueError('isolation exec helper absent')
    for case in ('normal','rx_delivery','tx_acceptance'):
        lines=re.findall(r'^PASS startup '+case+r' (.+)$',native,re.M)
        if any('creates=5 joins=5 binds=1 closes=1 callbacks=1 hres=1 timer=1' not in line or 'released=1 first=0' not in line for line in lines):
            raise ValueError('actual full-stack healthy proof differs: '+case)
    for case in set(STARTUP_CASES)-{'normal','rx_delivery','tx_acceptance'}:
        if any('released=0 first=' not in line for line in re.findall(r'^PASS startup '+case+r' (.+)$',native,re.M)):
            raise ValueError('failed run released stack resources: '+case)
    for case in ('partial_thread','socket_failure','startup_timeout','stop_pending'):
        lines=re.findall(r'^PASS startup '+case+r' (.+)$',native,re.M)
        if any('binds=0' not in line or 'callbacks=0 hres=0 timer=0 rx=0 tx=0' not in line for line in lines):
            raise ValueError('pending gate admitted work: '+case)
    for name in ('windows-final.log','linux-tests.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 380 tests' not in text or '\nOK\n' not in text or not text.rstrip().endswith('EXIT=0'):
            raise ValueError('380 Python regressions absent: '+name)
    text=(EVIDENCE/'linux-tests.log').read_text()
    for name,digest in inputs.items():
        if digest+'  stages/stage07-peripheral-partition/'+name not in text:raise ValueError('actual Linux input SHA absent: '+name)
    for name,reason in (('native-first.log','stats.first_error==kErrorEdrvInit && !closes && creates==1 && joins==1'),
                        ('native-second.log','oplk_process()==kErrorInvalidOperation && tx()==kErrorInvalidOperation')):
        text=(EVIDENCE/name).read_text()
        if reason not in text or not text.rstrip().endswith('EXIT=1'):raise ValueError('diagnostic failure missing/rewritten')
    from verify_powerlink_cn_p4d_checkpoint import private_evidence
    private_evidence() # Historical source/artifacts only, not executing old C.
    print('P4e SOFTWARE PASS: 25 control +25 private +17 real-stack/EDRV mocked-IO cases twice /380 Python /dual libraries; NOT real CN/MN interoperability',flush=True)
    return generated

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or sha(path.read_bytes())!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    old=STAGE/'tests/powerlink-cn-p4d-20261105'
    for line in (old/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('historical input omitted: '+name)
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and sha((REPO/name).read_bytes())!=digest:
            raise ValueError('historical source/evidence changed: '+name)
    return len(listed)

def source_check(destination,expected):
    tree=prepare(destination);env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(tree.parent))
    patch=STAGE/'source/powerlink/linux-cn/0001-rawsocket-aarch64-build.patch'
    for options in (['--check'],[],['--reverse','--check']):
        subprocess.run(['git','apply','--ignore-space-change']+options+[str(patch)],cwd=tree,env=env,check=True)
    if apply(tree)!=expected:raise ValueError('fresh source/startup overlay differs from dual builds')
    print('P4e SOURCE PASS: 1355 pinned files +immutable P4d baseline +startup overlay; exact 25 generated SHA',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    count=verify_manifest();generated=startup_evidence()
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    source_check(a.prepared,generated)
    print('P4e FRESH %s PASS: %d SHA /380 Python /pinned source+startup overlay; NO C/CN/BOARD IO' % (commit,count),flush=True)
