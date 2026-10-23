"""Compare actual compiled C packet codec against independent Python/zlib."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'board'))
from powerlink_edrv_checks import frame, OWN_MAC
if __name__ == '__main__':
    lines = subprocess.check_output([sys.argv[1], 'vector'], text=True).splitlines()
    peer = bytes.fromhex('025550330003')
    expected = [frame(OWN_MAC, peer, 0x35720001, sequence, 1).hex() for sequence in (0, 32)]
    if lines != expected: raise ValueError('Actual C codec differs from independent Python/zlib')
    print('P3e C/Python packet vectors match: 64/1514 bytes, nonce/role/sequence/pattern/CRC')
