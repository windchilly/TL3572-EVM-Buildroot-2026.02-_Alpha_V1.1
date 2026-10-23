"""Scoped P3d physical checkpoint: cumulative source, hardware inputs and evidence."""
import hashlib
from make_powerlink_p3d_manifest import inputs as previous_inputs, REPO, STAGE
EVIDENCE = STAGE / 'tests/powerlink-eth-p3d-hw-20261023'

def inputs():
    files = previous_inputs()
    files += [x for x in EVIDENCE.rglob('*') if x.is_file() and x.name not in
              ('SHA256SUMS', 'github-verification.log') and '__pycache__' not in x.parts]
    files += [STAGE / 'tests/board/up-b-m7-plk-eth.conf', STAGE / 'firmware/m7_eth2_power_hold.ko',
              STAGE / 'build/build_m7_eth2_power_hold.sh']
    files += [x for x in (STAGE / 'source/host/eth2-power-hold').iterdir() if x.is_file()]
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())

if __name__ == '__main__':
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + '  ' + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f'P3d HW manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes')
