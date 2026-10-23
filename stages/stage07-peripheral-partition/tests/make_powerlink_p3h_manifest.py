"""P3g raw hardware failure/recovery plus P3h software-only fix checkpoint."""
import hashlib
from make_powerlink_p3g_runner_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE = STAGE / 'tests/powerlink-nmt-p3h-20261023'
def inputs():
    files = previous_inputs()
    for name in ('powerlink-nmt-p3g-hw-20261023', 'powerlink-nmt-p3h-20261023'):
        files += [x for x in (STAGE / 'tests' / name).rglob('*') if x.is_file() and x.name not in
                  ('SHA256SUMS', 'github-verification.log') and '__pycache__' not in x.parts]
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())
if __name__ == '__main__':
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + '  ' + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f'P3h manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
