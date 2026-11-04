"""Replay recorded actual private bytes under fully FAKE board boundaries.
Simulation reports are NOT new board results, upload receipts or permission.
"""
import argparse
import json
from pathlib import Path
from test_powerlink_cycle_p3j_v2_board import V2WorkflowTests
CASES=('normal','abi','cold','liveproof','tcb','wrapper','lease','heap','bounds','publish','exception',
    'fault','ambiguous','start','stop','insmod','drift')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
    reports={}
    for case in CASES:
        result,calls,state=V2WorkflowTests().workflow(case)
        reports[case]=dict(simulated_result=result,system_calls=[list(x) for x in calls],simulated_final_state=state)
    with a.output.open('x',encoding='utf-8',newline='\n') as out:
        json.dump(dict(software_only=True,hardware_executed=False,cases=reports,
            limit='Actual historical TCB bytes replayed, all native/system/RPMsg boundaries FAKE. Not new hardware PASS.'),out,indent=2);out.write('\n')
    print('P3j-v2 SOFTWARE REPLAY PASS: %d scenarios, real private decoder, NO BOARD IO' % len(reports))
