"""P4f offline evidence/replay audit. No real census, markers, C/CN or board IO."""
import argparse,ast,hashlib,json,re,subprocess,sys,tempfile
from pathlib import Path
from make_powerlink_cn_p4f_manifest import SOURCE_INPUTS
from run_powerlink_cn_preflight_replay import replay
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4f-20261105'
def sha(data):return hashlib.sha256(data).hexdigest()

def preflight_evidence():
    inputs=json.loads((EVIDENCE/'input-sha256.json').read_text())
    if set(inputs)!={(STAGE/name).relative_to(REPO).as_posix() for name in SOURCE_INPUTS}:raise ValueError('source closure differs')
    for name,digest in inputs.items():
        if sha((REPO/name).read_bytes())!=digest:raise ValueError('source drift: '+name)
    for name in ('synthetic-policy.json','synthetic-snapshot.json','replay-report.json'):
        if (EVIDENCE/'windows-replay-final'/name).read_bytes()!=(EVIDENCE/'linux-replay-final'/name).read_bytes():raise ValueError('cross-platform replay differs: '+name)
    report=json.loads((EVIDENCE/'windows-replay-final/replay-report.json').read_text())
    if report['synthetic_only'] is not True or len(report['rejections'])!=32 or any(x['rejected'] is not True for x in report['rejections']):
        raise ValueError('synthetic mutation cases differ')
    for name in ('board_contacted','peer_executed','execution_allowed','runtime_ready'):
        if report[name] is not False:raise ValueError('offline boundary differs')
    if report['positive']['execution_allowed'] is not False or report['positive']['runtime_ready'] is not False:raise ValueError('replay incorrectly grants execution')
    with tempfile.TemporaryDirectory() as directory:
        replay(Path(directory)/'replay')
        for name in ('synthetic-policy.json','synthetic-snapshot.json','replay-report.json'):
            if (Path(directory)/'replay'/name).read_bytes()!=(EVIDENCE/'windows-replay-final'/name).read_bytes():raise ValueError('fresh deterministic replay differs')
    for name in ('windows-final.log','linux-final.log'):
        text=(EVIDENCE/name).read_text().replace('\r\n','\n')
        if 'Ran 434 tests' not in text or '\nOK\n' not in text or not text.rstrip().endswith('EXIT=0'):raise ValueError('434 Python regressions absent: '+name)
    native=(EVIDENCE/'linux-final.log').read_text()
    if native.count('Ran 19 tests')!=2:raise ValueError('real Linux window/FD suite not run twice')
    tree=ast.parse((STAGE/'tests/check_powerlink_cn_window_linux.py').read_text())
    suite=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='LinuxWindowTests')
    cases=[node.name for node in suite.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
    if len(cases)!=19:raise ValueError('native test declaration count changed')
    for name in cases:
        if len(re.findall(r'^'+name+r' .* \.\.\. ok$',native,re.M))!=2:raise ValueError('native case not passed twice: '+name)
    for name,digest in inputs.items():
        if digest+'  '+name not in native:raise ValueError('actual Linux source digest absent: '+name)
    failure=(EVIDENCE/'windows-targeted-first.log').read_text()
    if 'FAILED (failures=1, errors=3)' not in failure or not failure.rstrip().endswith('EXIT=1'):raise ValueError('cross-platform fixture failure omitted/overwritten')
    from verify_powerlink_cn_p4e_checkpoint import startup_evidence
    generated=startup_evidence() # Historical proof only, no new C/library build.
    for mode,digest in report['reused_library_sha256'].items():
        if sha((STAGE/'tests/powerlink-cn-p4e-20261105'/(mode+'-final')/'liboplkcn.a').read_bytes())!=digest:raise ValueError('P4e library changed')
    print('P4f SOFTWARE PASS: 434 Python /19 real-Linux storage+FD cases twice /1 synthetic positive+32 rejections byte-identical; P4e libraries unchanged, NOT runtime frontend or authorization',flush=True)
    return generated

def verify_manifest():
    listed=set()
    for line in (EVIDENCE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO)
        if name in listed or sha(path.read_bytes())!=digest:raise ValueError('SHA/duplicate: '+name)
        listed.add(name)
    for line in (STAGE/'tests/powerlink-cn-p4e-20261105/SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        if name not in listed:raise ValueError('P4e input omitted: '+name)
        if name not in ('memory.md','stages/stage07-peripheral-partition/README.md') and sha((REPO/name).read_bytes())!=digest:
            raise ValueError('immutable P4e source/artifact/evidence changed: '+name)
    return len(listed)

def source_check(destination,generated):
    from verify_powerlink_cn_p4e_checkpoint import source_check as unchanged
    unchanged(destination,generated)
    print('P4f SOURCE PASS: reuse exact P4e 25 generated files and library inputs; no C/ELF/UP2 change',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('prepared',type=Path);parser.add_argument('--expected-commit',required=True);args=parser.parse_args()
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if actual!=args.expected_commit:raise ValueError('unexpected Git checkout')
    count=verify_manifest();generated=preflight_evidence()
    subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    source_check(args.prepared,generated)
    print('P4f FRESH %s PASS: %d SHA /434 Python /synthetic replay /unchanged P4e sources; NO C/CN/HOST CENSUS/BOARD IO' % (actual,count),flush=True)
