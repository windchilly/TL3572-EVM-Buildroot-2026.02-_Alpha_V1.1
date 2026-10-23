"""Exact P3e source/build/physical evidence checkpoint; no user files/secrets."""
import hashlib
from make_powerlink_p3d_hw_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE = STAGE / 'tests/powerlink-edrv-p3e-20261023'

def inputs():
    files = previous_inputs()
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
              ('SHA256SUMS', 'github-verification.log') and '__pycache__' not in x.parts]
    files += [STAGE / 'tests/run_powerlink_edrv_probe_native.sh', STAGE / 'tests/board/up-b-m7-plk-edrv.conf']
    files += [REPO / 'docs/project/migration-plan.md']
    files += [STAGE / 'build/prepare_m7_powerlink.py']
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())

if __name__ == '__main__':
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + '  ' + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f'P3e manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
