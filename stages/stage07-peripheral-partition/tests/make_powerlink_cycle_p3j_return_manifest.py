"""P3j separately approved Linux-return checkpoint; historical inputs immutable."""
import hashlib
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cycle-p3j-return-20261104'
def inputs():
    old=STAGE/'tests/powerlink-cycle-p3j-hw-20261104'
    files=[REPO/line.split('  ',1)[1] for line in (old/'SHA256SUMS').read_text().splitlines()]
    files += [old/name for name in ('SHA256SUMS','github-verification.log','server-verification.log')]
    files += [x for x in (STAGE/'tests').glob('*') if x.is_file() and x.suffix in ('.py','.c','.sh')]
    files += [x for x in (STAGE/'tests/board').glob('*') if x.is_file() and x.suffix in ('.py','.conf')]
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
        ('SHA256SUMS','github-verification.log','server-verification.log') and '__pycache__' not in x.parts]
    return sorted(set(files),key=lambda x:x.relative_to(REPO).as_posix())
if __name__=='__main__':
    files=inputs()
    (EVIDENCE/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.relative_to(REPO).as_posix()
        for x in files)+'\n',encoding='utf-8',newline='\n')
    print('P3j Linux return manifest: %d files, %d bytes' % (len(files),sum(x.stat().st_size for x in files)))
