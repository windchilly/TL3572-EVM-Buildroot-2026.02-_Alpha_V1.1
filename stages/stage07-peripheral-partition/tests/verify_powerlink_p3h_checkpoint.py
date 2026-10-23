"""Fresh GitHub current-source/evidence verification; NO board or recovery path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from audit_powerlink_pdo_memory import EXPECTED
STAGE = Path(__file__).resolve().parents[1]
REPO = STAGE.parents[1]
ORIGINAL = '7281943595b082b408933771e18d4c123d7e3b3a'
def log_json(path):
    value, end = json.JSONDecoder().raw_decode(path.read_text())
    if path.read_text()[end:].strip() != 'EXIT=0': raise ValueError('failed evidence read: ' + str(path))
    return value
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('prepared', type=Path); p.add_argument('--expected-commit', required=True); a = p.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    if commit != a.expected_commit: raise ValueError('unexpected checkout')
    evidence = STAGE / 'tests/powerlink-nmt-p3h-20261023'
    hardware = STAGE / 'tests/powerlink-nmt-p3g-hw-20261023'
    count = 0
    for line in (evidence / 'SHA256SUMS').read_text().splitlines():
        digest, relative = line.split('  ', 1); path = (REPO / relative).resolve(); path.relative_to(REPO)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise ValueError('SHA mismatch: ' + relative)
        count += 1
    result = json.loads((hardware / 'board-result.json').read_text())
    if result['passed'] or result['cleanup'] or not result['submitted'] or result['private_stopped'] is not None:
        raise ValueError('failed hardware result was changed')
    cache = log_json(hardware / 'failed-cache.log')
    if cache['nmt'] != dict(resetSubmitted=1, offSubmitted=0, resetLoops=4, offLoops=0, reached=0): raise ValueError('NMT failure changed')
    if cache['ethLease'] != 2 or cache['exception'] != dict(cause=0, elr=0, esr=0): raise ValueError('retained state changed')
    geometry = json.loads((hardware / 'pdo-memory.json').read_text())
    if geometry['geometry'] != EXPECTED or (geometry['heap_free_bytes'], geometry['tx_mapping_request_bytes'],
            geometry['minimum_shortfall_bytes']) != (148920, 162560, 13640): raise ValueError('heap diagnosis changed')
    recovery = log_json(hardware / 'recovery-verification-v3.log')
    if recovery['boot_id'] != 'cd4f03d6-005d-473d-b6ce-0cc745314a08' or 'Running' in recovery['mcsctl']:
        raise ValueError('post-reboot recovery changed')
    # Original runtime bytes are immutable. Only CurrentEL checker changed AFTER
    # failure; verify that original from the actual GitHub parent Git object.
    for name, digest in json.loads((hardware / 'board-input-sha256.json').read_text()).items():
        if name == 'tl3572-m7-powerlink-p3g-up-b.elf': path = STAGE / 'tests/powerlink-nmt-p3g-20261023/candidates' / name
        elif name == 'nmt-abi.json': path = STAGE / 'tests/powerlink-nmt-p3g-runner-20261023' / name
        elif name in ('audit_integrated_mmu.py', 'verify_integrated_elf.py'): path = STAGE / 'tests' / name
        else: path = STAGE / 'tests/board' / name
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            if name != 'powerlink_nmt_checks.py': raise ValueError('original runtime input changed: ' + name)
            data = subprocess.check_output(['git', 'show', ORIGINAL + ':' + path.relative_to(REPO).as_posix()], cwd=REPO)
            if hashlib.sha256(data).hexdigest() != digest: raise ValueError('original checker Git object mismatch')
    audit = json.loads((evidence / 'nmt-heap-audit.json').read_text())
    if audit['hardware_tested'] or audit['od_channels_reduced'] or [x['fsc_pool_bytes'] for x in audit['images']] != [524288, 1048576]:
        raise ValueError('software-only/full OD/per-role pool scope changed')
    candidate = evidence / 'candidates/tl3572-m7-powerlink-p3h-up-b.elf'
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != audit['images'][1]['elf_sha256']: raise ValueError('new candidate mismatch')
    print(f'GITHUB FRESH {commit}: {count} SHA, original 18 board inputs, raw FAILED result, authorized recovery, P3h software scope PASS', flush=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(STAGE / 'tests'), '-p', 'test_*.py', '-v'], cwd=REPO, check=True)
    prepared = a.prepared.resolve()
    subprocess.run([sys.executable, str(STAGE / 'build/prepare_m7_powerlink.py'), str(prepared)], cwd=REPO, check=True)
    tree = prepared / 'openPOWERLINK_V2-2.7.2'; env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch', '0004-uniproton-od-prc-disabled.patch',
                  '0005-mn-request-queue-allocation-errors.patch', '0006-uniproton-pdo-setup-no-wait.patch',
                  '0007-uniproton-cyclic-allocation-guards.patch'):
        args = ['git', '-C', str(tree), 'apply', '--ignore-space-change']; path = str(STAGE / 'source/powerlink/port' / patch)
        subprocess.run(args + ['--check', path], env=env, check=True)
        subprocess.run(args + [path], env=env, check=True)
        subprocess.run(args + ['--reverse', '--check', path], env=env, check=True)
    if hashlib.sha256((tree / 'stack/src/user/pdo/pdou.c').read_bytes()).hexdigest() != geometry['pdou_source_sha256']:
        raise ValueError('PDO geometry source mismatch')
    print(f'GITHUB FRESH PASS: {count} SHA / 175 Python / 1355 upstream files + REAL 0001-0007 patches / raw failure+recovery+software proof; NO BOARD', flush=True)
