"""P3h independent runner/heap gates/ABI evidence; historical manifests stay fixed."""
import hashlib
from make_powerlink_p3h_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE=STAGE/'tests/powerlink-nmt-p3h-runner-20261023'
def inputs():
    files=previous_inputs()
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
        ('SHA256SUMS','github-verification.log') and '__pycache__' not in x.parts]
    files += [STAGE/'tests/board/up-b-m7-plk-nmt-p3h.conf',STAGE/'tests/powerlink-nmt-p3h-20261023/github-verification.log']
    return sorted(set(files),key=lambda x:x.relative_to(REPO).as_posix())
if __name__=='__main__':
    files=inputs()
    (EVIDENCE/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.relative_to(REPO).as_posix() for x in files)+'\n',encoding='utf-8',newline='\n')
    print(f'P3h runner manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
