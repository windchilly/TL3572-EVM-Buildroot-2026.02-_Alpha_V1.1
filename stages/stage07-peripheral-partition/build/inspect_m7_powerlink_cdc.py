"""Read-only P4a CDC inspection, NOT an OD/XDD/device or deployment validator.
Preserves ordered writes (PDO reconfiguration can write an index repeatedly).
The bounds/trailing/empty-data rules are a project audit subset, not DS301.
No firmware changes, socket, SSH, board commands or configuration generation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import tarfile
from prepare_m7_powerlink import validate_members

STAGE=Path(__file__).resolve().parents[1]
MAX_BYTES=1024*1024
MAX_ENTRIES=4096

def sha(data):return hashlib.sha256(data).hexdigest()

def inspect_cdc(data,scope='unknown'):
    if scope not in ('unknown','mn','cn'):raise ValueError('scope must be unknown, mn or cn')
    if not 4<=len(data)<=MAX_BYTES:raise ValueError('CDC size outside offline audit limit')
    count=struct.unpack_from('<I',data)[0]
    if not 1<=count<=MAX_ENTRIES:raise ValueError('CDC record count outside offline audit limit')
    offset=4;entries=[]
    for sequence in range(count):
        if len(data)-offset<7:raise ValueError('truncated CDC record header')
        index,subindex,size=struct.unpack_from('<HBI',data,offset);offset+=7
        if not size or size>len(data)-offset:raise ValueError('empty/truncated CDC record data')
        value=data[offset:offset+size];offset+=size
        entry=dict(sequence=sequence,index=f'0x{index:04x}',subindex=subindex,bytes=size,sha256=sha(value))
        if size<=32:entry['data_hex']=value.hex()
        if index==0x1006 and subindex==0 and size==4:entry['cycle_us']=int.from_bytes(value,'little')
        if scope=='mn' and index==0x1f81 and 1<=subindex<=254 and size==4:
            entry['node_assignment_raw']=f'0x{int.from_bytes(value,"little"):08x}'
        if scope=='mn' and index==0x1f22 and 1<=subindex<=254:
            # Explicit MN context only: one CFM domain -> CN concise config.
            # CN/unknown context never guesses nested domains or identities.
            entry['cn_concise_config']=inspect_cdc(value,'cn')
        entries.append(entry)
    if offset!=len(data):raise ValueError('trailing CDC bytes outside strict audit subset')
    return dict(scope=scope,bytes=len(data),sha256=sha(data),count=count,entries=entries,
        structural_subset_passed=True,device_semantics_validated=False,runtime_ready=False,
        limit='Ordered CDC bytes only; no OD access/type/range/CFM identity/PDO timing or deployment approval.')

def baseline_report():
    root=STAGE/'source/powerlink';lock=json.loads((root/'upstream.lock.json').read_text())
    archive=root/lock['archive'];raw=archive.read_bytes()
    if len(raw)!=lock['archive_bytes'] or sha(raw)!=lock['archive_sha256']:raise ValueError('upstream archive differs from lock; fetch Git LFS')
    names=('stack/src/user/obd/obdcdc.c','apps/common/objdicts/CiA302-4_MN/objdict.h','stack/include/oplk/oplkdefs.h')
    with tarfile.open(archive,'r:gz') as tar:
        validate_members(tar.getmembers(),lock['archive_prefix'],lock['files'])
        if tar.pax_headers.get('comment')!=lock['commit']:raise ValueError('upstream commit mismatch')
        upstream={name:tar.extractfile(lock['archive_prefix']+'/'+name).read() for name in names}
    port=root/'port';mn=(port/'m7_mn.c').read_text();probe=(port/'m7_cycle_probe.c').read_text()
    decoder=(STAGE/'tests/board/powerlink_cycle_p3j_checks.py').read_text()
    match=re.search(r'static const uint8_t cdc\[\] = \{([^}]+)\}',mn)
    if not match:raise ValueError('reviewed built-in CDC declaration changed')
    cdc=bytes(int(value.strip(),0) for value in match.group(1).split(','))
    decoded=inspect_cdc(cdc,'mn')
    checks=dict(mn_node_f0='init.nodeId = 0xf0' in mn,
        complete_assignment_scan='for (i=1;i<=254;++i)' in probe and 'bytes!=4 || value' in probe and '0x1f81' in probe,
        rejects_any_rx='if (life->rx || life->rxErrors' in probe,
        decoder_rejects_rx="'timerAfter','rx','rxErrors'" in decoder,
        original_minimal_cdc=cdc==bytes.fromhex('0100000006100004000000e8030000'))
    if not all(checks.values()):raise ValueError('pinned no-CN baseline changed; review, do not loosen this audit')
    runtime=json.loads((STAGE/'tests/powerlink-cycle-p3j-v2-20261104/runtime-inputs.json').read_text())
    candidate=runtime['files']['tl3572-m7-powerlink-p3j-up-b.elf']
    path=STAGE.parents[1]/candidate['path']
    if sha(path.read_bytes())!=candidate['sha256']:raise ValueError('pinned P3j candidate changed')
    return dict(software_only=True,board_contacted=False,upstream_commit=lock['commit'],
        archive_sha256=lock['archive_sha256'],upstream_files=lock['files'],
        source_sha256={name:sha(value) for name,value in upstream.items()},
        local_source_sha256={name:sha((STAGE/name).read_bytes()) for name in
            ('source/powerlink/port/m7_mn.c','source/powerlink/port/m7_cycle_probe.c','tests/board/powerlink_cycle_p3j_checks.py')},
        candidate_sha256=candidate['sha256'],baseline_checks=checks,builtin_cdc=decoded,
        cn_capable=False,runtime_ready=False,
        required_changes=['Separate CN-capable candidate and bounded owner/decoder; preserve P3j no-CN history.',
            'Reviewed device identity, node assignment, MN+CN OD/PDO mappings and safe output values.',
            'CN/SDO/CFM/application event handling, process-image exchange and RX acceptance tests.',
            'New memory/timing/failure-stop proof and separately approved isolated hardware window.'])

def write_report(path,report):
    with path.open('x',encoding='utf-8',newline='\n') as out:json.dump(report,out,indent=2);out.write('\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--baseline',action='store_true');source.add_argument('--cdc',type=Path)
    parser.add_argument('--scope',choices=('unknown','mn','cn'),default='unknown')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.cdc:
        if args.cdc.stat().st_size>MAX_BYTES:raise ValueError('CDC exceeds offline audit byte limit')
        report=inspect_cdc(args.cdc.read_bytes(),args.scope)
    else:report=baseline_report()
    if args.output:write_report(args.output,report)
    else:print(json.dumps(report,indent=2))
