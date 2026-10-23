"""Exact failed P3f physical checkpoint, no automatic recovery or repair."""
import hashlib
from make_powerlink_p3f_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE = STAGE / 'tests/powerlink-mn-p3f-hw-20261023'
def inputs():
    files = previous_inputs()
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
              ('SHA256SUMS', 'github-verification.log') and '__pycache__' not in x.parts]
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())
if __name__ == '__main__':
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + '  ' + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f'P3f HW failure manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
