"""P3j fresh source/candidate/old evidence verification, NO board paths executed."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
from audit_powerlink_cycle_probe import LAYOUT
from verify_integrated_elf import symbols_and_data
from verify_powerlink_cycle_checkpoint import software_evidence,verify_evidence
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
SHA='4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35'
def guard_evidence():
    evidence=STAGE/'tests/powerlink-cycle-p3j-20261102'
    image=evidence/'candidates/tl3572-m7-powerlink-p3j-up-b.elf'
    if hashlib.sha256(image.read_bytes()).hexdigest()!=SHA:raise ValueError('unreviewed candidate')
    symbols=symbols_and_data(image)
    for name,size in (('snapshot',1504),('cycleResult',608),('cycleReady',4),('cycleAttempted',4)):
        if symbols[name][1]!=size:raise ValueError('BSS ABI mismatch: '+name)
    for name in ('candidate-final-audit.json','candidate-repro-audit.json'):
        audit=json.loads((evidence/name).read_text())
        if (audit['hardware_tested'] is not False or audit['cycle_layout_native']!=LAYOUT or audit['cycle_layout_aarch64']!=LAYOUT or
            audit['final_undefined_symbols'] or audit['old_snapshot_bytes']!=1504 or not audit['rpmsg_stack_budget']['passed']):raise ValueError('candidate proof changed')
        for symbol,value in audit['cycle_private_symbols'].items():
            if list(symbols[symbol][:2])!=value:raise ValueError('private addresses differ from pinned image')
    repro=json.loads((evidence/'repro.json').read_text())
    if repro['identical'] is not True or len(repro['artifacts'])!=11 or repro['hardware_tested'] is not False:raise ValueError('double build proof missing')
    log=(evidence/'linux-final-fixed.log').read_text()
    cases=('normal','heap_full','heap_small','context','no_completion','no_progress','late','dma_fault','tx_error','wrong_context',
        'nmt_timeout','reset_command','off_command','stop_cycle_failure','stop_failure','timer_release_failure','readback','total_budget')
    for case in cases:
        if 'P3j native production diagnostic '+case+' PASS' not in log:raise ValueError('native scenario missing: '+case)
    for phrase in ('no_completion result=0x305','no_progress result=0x306','stop_cycle_failure result=0x30b',
        'heap_small result=0x302 stack=0xb3','result=0x0 stack=0x0 clean=1 stage=9','Ran 215 tests','REMOTE_EXIT=0'):
        if phrase not in log:raise ValueError('guard/first-error proof missing: '+phrase)
    for name in ('windows.log','linux-final-fixed.log'):
        text=(evidence/name).read_text()
        if 'Ran 215 tests' not in text or not text.rstrip().endswith('EXIT=0'):raise ValueError('regression missing')
    print('P3j guard/one-shot owner/candidate 608+1504 ABI /18+4 native /11 identical artifacts PASS; NO BOARD',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared',type=Path);p.add_argument('--expected-commit',required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if commit!=a.expected_commit:raise ValueError('unexpected checkout')
    manifest=STAGE/'tests/powerlink-cycle-p3j-20261102/SHA256SUMS';listed=set()
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1);path=(REPO/name).resolve();path.relative_to(REPO);listed.add(name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('SHA mismatch: '+name)
    if 'stages/stage07-peripheral-partition/tests/run_powerlink_cycle_probe_native.sh' not in listed:raise ValueError('native script missing from manifest')
    guard_evidence();software_evidence();verify_evidence()
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(STAGE/'tests'),'-p','test_*.py','-v'],cwd=REPO,check=True)
    prepared=a.prepared.resolve();subprocess.run([sys.executable,str(STAGE/'build/prepare_m7_powerlink.py'),str(prepared)],cwd=REPO,check=True)
    tree=prepared/'openPOWERLINK_V2-2.7.2';env=dict(os.environ,GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch','0004-uniproton-od-prc-disabled.patch','0005-mn-request-queue-allocation-errors.patch',
        '0006-uniproton-pdo-setup-no-wait.patch','0007-uniproton-cyclic-allocation-guards.patch'):
        args=['git','-C',str(tree),'apply','--ignore-space-change'];path=str(STAGE/'source/powerlink/port'/patch)
        for options in (['--check'],[],['--reverse','--check']):subprocess.run(args+options+[path],env=env,check=True)
    print(f'P3j FRESH {commit} PASS: {len(listed)} SHA /215 Python /1355 files + real0001-0007 /candidate; NO BOARD',flush=True)
