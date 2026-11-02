"""P3i software cycle evidence, all reproducible inputs; old manifests fixed."""
import hashlib
from make_powerlink_p3h_hw_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE=STAGE/'tests/powerlink-cycle-p3i-20261102'
def inputs():
    files=previous_inputs()
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
        ('SHA256SUMS','github-verification.log','server-verification.log') and '__pycache__' not in x.parts]
    files += [STAGE/'tests/powerlink-nmt-p3h-hw-20261023'/name for name in ('github-verification.log','server-verification.log')]
    files += [STAGE/'tests/run_powerlink_cycle_native.sh']
    return sorted(set(files),key=lambda x:x.relative_to(REPO).as_posix())
if __name__=='__main__':
    files=inputs()
    (EVIDENCE/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.relative_to(REPO).as_posix() for x in files)+'\n',encoding='utf-8',newline='\n')
    print(f'P3i manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
