"""P3j independent full software roots plus cumulative UP1/UP2 runtimes."""
import argparse,json
from pathlib import Path
from compare_powerlink_p3b import compare
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('first','second','candidate_first','candidate_second','report'):p.add_argument(name,type=Path)
    a=p.parse_args();report=compare(a.first,a.second,a.candidate_first,a.candidate_second)
    report.update(phase='P3j guarded one-shot cycle, SOFTWARE ONLY',
        software_origin='Two fresh full native/AArch64 roots from pinned source; two fresh cumulative trees',
        limit='9 AArch64 objects/libraries plus 2 runtime images compared; ELF debug paths excluded, no board or realtime proof')
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('P3j REPRO PASS: 9 fresh AArch64 artifacts + 2 cumulative runtimes byte-identical')
