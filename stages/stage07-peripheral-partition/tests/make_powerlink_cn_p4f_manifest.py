"""P4f exact inputs plus immutable P4e; two posterior audit logs excluded."""
import argparse,hashlib,json
from pathlib import Path
STAGE=Path(__file__).resolve().parents[1];REPO=STAGE.parents[1]
EVIDENCE=STAGE/'tests/powerlink-cn-p4f-20261105'
SOURCE_INPUTS=('tests/board/powerlink_cn_preflight.py','tests/board/collect_powerlink_cn_preflight.py',
    'tests/board/powerlink_cn_window.py','config/powerlink-cn-preflight.template.json',
    'tests/test_powerlink_cn_preflight.py','tests/check_powerlink_cn_window_linux.py',
    'tests/run_powerlink_cn_preflight_replay.py','tests/verify_powerlink_cn_p4f_checkpoint.py',
    'tests/make_powerlink_cn_p4f_manifest.py','tests/board/eth3-recovery-20261009/final.json')
def inputs():
    old=STAGE/'tests/powerlink-cn-p4e-20261105'
    files=[REPO/line.split('  ',1)[1] for line in (old/'SHA256SUMS').read_text().splitlines()]
    files += [old/name for name in ('SHA256SUMS','github-verification.log','server-verification.log')]
    files += [STAGE/name for name in SOURCE_INPUTS]
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
        ('SHA256SUMS','github-verification.log','server-verification.log') and '__pycache__' not in x.parts]
    return sorted(set(files),key=lambda x:x.relative_to(REPO).as_posix())
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs-only',action='store_true');args=parser.parse_args()
    if args.inputs_only:
        data={str((STAGE/name).relative_to(REPO).as_posix()):hashlib.sha256((STAGE/name).read_bytes()).hexdigest() for name in SOURCE_INPUTS}
        with (EVIDENCE/'input-sha256.json').open('x',encoding='utf-8',newline='\n') as file:json.dump(data,file,indent=2,sort_keys=True);file.write('\n')
        print('P4f locked %d source inputs' % len(data))
    else:
        files=inputs();(EVIDENCE/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.relative_to(REPO).as_posix()
            for x in files)+'\n',encoding='utf-8',newline='\n')
        print('P4f manifest: %d files, %d bytes' % (len(files),sum(x.stat().st_size for x in files)))
