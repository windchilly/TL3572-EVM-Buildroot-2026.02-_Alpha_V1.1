"""Decode actual HOST production result; mailbox synthesized, NOT board proof."""
import argparse
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'board'))
from powerlink_cycle_p3j_checks import decode_cycle,validate_snapshot,validate_reply,validate_owner,match_replies,PUBLIC
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('result',type=Path);a=p.parse_args()
    raw=a.result.read_bytes(); decoded=decode_cycle(raw);life,c=decoded['lifecycle'],decoded['cycle']
    mailbox=bytearray(1504);struct.pack_into('<9I',mailbox,0,1,0,0,1,1,8,0,0,c['owner'])
    mailbox[40:80]=raw[168:208]
    report=validate_snapshot(mailbox,raw,1,1)
    reply=validate_reply('PLK UP2 CYCLE '+' '.join(k+'='+v for k,v in (PUBLIC | dict(loops=str(life['loops']),
        run=str(c['runLoops']),drain=str(c['drainLoops']),tx=str(life['tx']))).items()))
    owner=dict(ready='1',pending='0',running='0',seq='1',done='1',cmd='8',rc='0x0',runtime='0x0',
        state='0',nmt='0x0',owner=str(c['owner']),processes=str(life['final']['processes']),
        events=str(life['final']['events']),mode='bounded-cycle-diagnostic')
    match_replies(report,owner,reply)
    print('P3j HOST actual608B decoder PASS: loops=%d tx=%d events=%d; SYNTHESIZED mailbox, NO BOARD' %
        (life['loops'],life['tx'],life['final']['events']))
