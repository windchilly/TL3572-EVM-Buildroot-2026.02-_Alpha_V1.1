"""P3j exact production guard/owner/candidate source and evidence checkpoint."""
import hashlib
from make_powerlink_cycle_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-20261102'
def inputs():
    files=previous_inputs()
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
        ('SHA256SUMS','github-verification.log','server-verification.log') and '__pycache__' not in x.parts]
    files += [STAGE/'tests/run_powerlink_cycle_probe_native.sh']
    files += [STAGE/'tests/powerlink-cycle-p3i-20261102'/name for name in ('github-verification.log','server-verification.log')]
    return sorted(set(files),key=lambda x:x.relative_to(REPO).as_posix())
if __name__=='__main__':
    files=inputs()
    (EVIDENCE/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.relative_to(REPO).as_posix() for x in files)+'\n',encoding='utf-8',newline='\n')
    print(f'P3j manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
