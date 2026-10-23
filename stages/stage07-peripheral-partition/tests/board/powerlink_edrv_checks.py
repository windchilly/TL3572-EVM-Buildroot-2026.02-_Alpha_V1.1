"""Pure P3e codec/result checks. No network, board IO or imports with side effects."""
import struct
import zlib
from powerlink_eth_checks import fields, quiescent
OWN_MAC = bytes.fromhex('025550320002')
MAGIC = b'M7EDRV01'
EACH = 32
TOTAL = 64

def frame(destination, source, nonce, sequence, role):
    if len(destination) != 6 or len(source) != 6 or not 0 <= sequence < TOTAL or role not in (1, 2):
        raise ValueError('invalid bounded P3e frame arguments')
    length = 64 if sequence < EACH else 1514
    record = MAGIC + struct.pack('!4I', nonce, role, sequence, length - 42)
    record += bytes((nonce + sequence + i) & 255 for i in range(length - 42))
    return destination + source + bytes.fromhex('88b5') + record + struct.pack('!I', zlib.crc32(record))

def validate_result(reply):
    result = fields(reply, 'PLK UP2 EDRV')
    if not quiescent(result) or result.get('rc') != '0': raise ValueError('EDRV failed or stop unproved')
    if any(result.get(k) != '64' for k in ('rx', 'submitted', 'tx', 'fcs')):
        raise ValueError('incomplete physical frame/callback/FCS counts')
    if any(result.get(k) != '0' for k in ('rxerr', 'txerr', 'fatal')): raise ValueError('EDRV hardware errors')
    if int(result['mac'], 0) & 0x0030e003 != 0xc003: raise ValueError('MAC not enabled100-half')
    return result

def accept_response(packet, address, expected, nonce):
    # AF_PACKET can return the locally transmitted request. Never count it.
    if address[2] == 4 or len(packet) < 26 or packet[12:22] != b'\x88\xb5' + MAGIC:
        return False
    if struct.unpack_from('!I', packet, 22)[0] != nonce: return False
    if packet != expected: raise ValueError('peer received corrupt/wrong-role/sequence P3e response')
    return True
