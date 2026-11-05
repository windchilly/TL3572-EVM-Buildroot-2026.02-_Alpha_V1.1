"""P4f deterministic synthetic replay report; no host/board collection or CN."""
import argparse,copy,json
from pathlib import Path
from test_powerlink_cn_preflight import fixture,set_at,FRAME_MUTATIONS,POLICY_MUTATIONS,NOW,gates

def replay(destination):
    if destination.exists():raise FileExistsError('fresh synthetic replay directory required')
    destination.mkdir(parents=True)
    policy,snapshot=fixture();positive=gates.check(snapshot,policy,NOW);results=[]
    for kind,mutations in (('frame',FRAME_MUTATIONS),('policy',POLICY_MUTATIONS)):
        for name,(path,value) in sorted(mutations.items()):
            bad_policy,bad_snapshot=copy.deepcopy(policy),copy.deepcopy(snapshot)
            if kind=='policy':set_at(bad_policy,path,value)
            else:
                for frame in bad_snapshot['frames']:set_at(frame,path,value)
            try:gates.check(bad_snapshot,bad_policy,NOW)
            except ValueError as error:results.append(dict(case=kind+'/'+name,rejected=True,reason=str(error)))
            else:raise AssertionError('unsafe mutation accepted: '+name)
    report=dict(schema='m7-cn-preflight-replay-v1',synthetic_only=True,board_contacted=False,peer_executed=False,
        execution_allowed=False,runtime_ready=False,positive=positive,rejections=results,
        reused_library_sha256=dict(native='f0c7e1e9c810518bce3ff55878de04c28b857e7a6748b315f243364e186b2f68',
            aarch64='a29e046a5c107511eb8c6341d0310edf47fbfd96d5cdb09df366305ac9072e5b'))
    for name,data in (('synthetic-policy.json',policy),('synthetic-snapshot.json',snapshot),('replay-report.json',report)):
        with (destination/name).open('x',encoding='utf-8',newline='\n') as file:json.dump(data,file,indent=2,sort_keys=True);file.write('\n')
    print('P4f REPLAY PASS: 1 evidence-only positive /%d fail-closed mutations /NO CN OR HOST COLLECTION' % len(results),flush=True)
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path);args=parser.parse_args();replay(args.destination)
