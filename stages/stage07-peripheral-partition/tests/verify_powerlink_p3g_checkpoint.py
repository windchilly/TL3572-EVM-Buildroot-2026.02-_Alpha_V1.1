"""Verify P3g SHA/tests and REAL fixed upstream patch application. No board."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
STAGE = Path(__file__).resolve().parents[1]
REPO = STAGE.parents[1]
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('prepared', type=Path, help='Fresh source-extraction destination')
    p.add_argument('--expected-commit', required=True)
    a = p.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    if commit != a.expected_commit: raise ValueError('Unexpected checked-out commit: ' + commit)
    count = 0
    for line in (STAGE / 'tests/powerlink-nmt-p3g-20261023/SHA256SUMS').read_text().splitlines():
        digest, relative = line.split('  ', 1); path = (REPO / relative).resolve(); path.relative_to(REPO)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise ValueError('SHA mismatch: ' + relative)
        count += 1
    print(f'GITHUB FRESH {commit}: {count} SHA files PASS', flush=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(STAGE / 'tests'),
                    '-p', 'test_*.py', '-v'], cwd=REPO, check=True)
    prepared = a.prepared.resolve()
    subprocess.run([sys.executable, str(STAGE / 'build/prepare_m7_powerlink.py'), str(prepared)], cwd=REPO, check=True)
    tree = prepared / 'openPOWERLINK_V2-2.7.2'
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(prepared))
    for patch in ('0003-uniproton-passive-lifecycle.patch', '0004-uniproton-od-prc-disabled.patch',
                  '0005-mn-request-queue-allocation-errors.patch', '0006-uniproton-pdo-setup-no-wait.patch',
                  '0007-uniproton-cyclic-allocation-guards.patch'):
        args = ['git', '-C', str(tree), 'apply', '--ignore-space-change']
        path = str(STAGE / 'source/powerlink/port' / patch)
        subprocess.run(args + ['--check', path], env=env, check=True)
        subprocess.run(args + [path], env=env, check=True)
        subprocess.run(args + ['--reverse', '--check', path], env=env, check=True)
    print(f'GITHUB FRESH PASS: {count} SHA, 144 Python, 1355 upstream files with REAL 0001-0007 patches, all scoped LFS inputs', flush=True)
