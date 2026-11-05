"""P4f pure Linux-CN preflight checks. Replayed data is NOT authority to execute.
No IO at import, no socket/stack calls, no mutation or recovery commands.
The future frontend must obtain fresh human approval and recheck under its lock.
"""
import hashlib,json,re,uuid
from pathlib import PurePosixPath

SCHEMA='m7-cn-preflight-v1'
MAX_AGE_NS=2_000_000_000
MAX_SPAN_NS=5_000_000_000
LIMITS=dict(lease_ns=8_000_000_000,max_tx=2048,max_rx=4096,node_id=1,cycle_us=1000)
DRIVER='/sys/bus/usb/drivers/sr9900'
MGMT_DRIVER='/sys/bus/platform/drivers/rk_gmac-dwmac'
OLD_DEMO_SHA='bc53889dd0c682ac4bec79e28e1e15d6254d82b281f5426f62487d02b26eb053'
DENIED_PROCESSES={'demo_cn_console','demo_mn_console','tcpdump','dumpcap','tshark',
    'eth3_l2_smoke.py','run_eth_direct.py','run_powerlink_edrv_probe.py'}

def require(condition,reason):
    if not condition:raise ValueError(reason)

def keys(value,names):
    require(type(value) is dict and set(value)==set(names.split()),'missing/unknown fields: '+names)

def integer(value,minimum=0,maximum=2**64-1):
    require(type(value) is int and minimum<=value<=maximum,'invalid integer')
    return value

def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'invalid SHA256')
    return value

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(value):return hashlib.sha256(canonical(value)).hexdigest()

def unique_json(text):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key: '+k);out[k]=v
        return out
    require(len(text.encode())<=4*1024*1024,'oversized JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=lambda x:require(False,'nonfinite JSON'))

def uuid_text(value):
    require(type(value) is str and str(uuid.UUID(value))==value,'noncanonical UUID')
    return value

def absolute(value):
    require(type(value) is str and value.startswith('/') and '\x00' not in value and
        '..' not in value.split('/') and str(PurePosixPath(value))==value,'noncanonical absolute path')
    return value

def mac(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{2}(:[0-9a-f]{2}){5}',value) and
        not int(value[:2],16)&1 and value!='00:00:00:00:00:00','invalid unicast MAC')

def packet_table(text):
    lines=text.splitlines();require(lines and lines[0].split()==['sk','RefCnt','Type','Proto','Iface','R','Rmem','User','Inode'],
        'unknown packet socket table header')
    require(len(lines)<=4097,'too many packet sockets');out=[];inodes=set()
    for line in lines[1:]:
        columns=line.split();require(len(columns)==9,'malformed packet socket row')
        require(re.fullmatch('[0-9a-fA-F]+',columns[0]) and re.fullmatch('[0-9a-fA-F]{4}',columns[3]),'bad packet hex')
        values=[int(columns[i],10) for i in (1,2,4,5,6,7,8)]
        ref,kind,iface,running,rmem,uid,inode=values
        require(ref>0 and kind in (2,3) and iface>=-1 and running in (0,1) and rmem>=0 and uid>=0 and inode>0 and inode not in inodes,'bad packet values')
        inodes.add(inode);out.append(dict(ifindex=iface,protocol=int(columns[3],16),inode=inode))
    return out

def elf_report(header,program,dynamic,versions):
    def field(name):
        values=re.findall(r'^\s*'+name+r':\s*(.+)$',header,re.M)
        require(len(values)==1,'missing/duplicate ELF '+name);return values[0].strip()
    require(field('Class')=='ELF64' and field('Data')=="2's complement, little endian" and field('Machine')=='AArch64','ELF architecture')
    require(field('Type').split()[0] in ('EXEC','DYN'),'not an executable/shared ELF')
    interpreters=re.findall(r'\[Requesting program interpreter: ([^\]]+)\]',program)
    require(len(interpreters)<=1,'multiple ELF interpreters')
    require(not re.search(r'GNU_STACK[^\n]*\bRWE\b',program),'executable stack')
    require(not re.search(r'\((?:RPATH|RUNPATH|AUDIT|DEPAUDIT|FILTER|AUXILIARY)\)',dynamic),'dynamic injection/search path')
    needed=re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]',dynamic)
    require(len(needed)==len(set(needed)) and len(needed)<=8,'duplicate/excess ELF dependencies')
    require(all(re.fullmatch('[A-Za-z0-9_.+-]+',x) for x in needed),'nonlocal ELF dependency')
    needs={};counts={};definitions=[];mode=None;current=None
    for line in versions.splitlines():
        if line.startswith('Version needs section '):mode='needs';current=None
        elif line.startswith('Version definition section '):mode='definitions';current=None
        elif line.startswith('Version symbols section '):mode=None;current=None
        if mode=='needs':
            file=re.search(r'\bFile: (\S+)\s+Cnt: (\d+)',line)
            if file:
                current=file[1];require(current not in needs,'duplicate version provider');needs[current]=[];counts[current]=int(file[2])
            name=re.search(r'\bName: (\S+)',line)
            if name:
                require(current is not None,'version without provider');needs[current].append(name[1])
        elif mode=='definitions':
            name=re.search(r'\bName: (\S+)',line)
            if name:definitions.append(name[1])
    require(all(len(v)==len(set(v)) and v for v in needs.values()),'empty/duplicate needed versions')
    require(all(len(v)==counts[name] for name,v in needs.items()),'truncated version requirements')
    require(len(definitions)==len(set(definitions)),'duplicate provided versions')
    return dict(interpreter=interpreters[0] if interpreters else None,needed=needed,needs=needs,definitions=definitions)

def policy_check(policy):
    keys(policy,'schema runtime_ready boot_id kernel namespaces interface management artifact objects limits')
    require(policy['schema']==SCHEMA and policy['runtime_ready'] is False,'policy role/version')
    uuid_text(policy['boot_id']);require(policy['kernel']=='6.12.69-gf1b67c293213','kernel not pinned M6')
    keys(policy['namespaces'],'net pid user')
    for kind,value in policy['namespaces'].items():
        require(type(value) is str and re.fullmatch(kind+r':\[[0-9]+\]',value),'namespace unpinned')
    cn=policy['interface'];keys(cn,'name ifindex mac driver device')
    require(cn['name']=='eth2' and cn['driver']==DRIVER,'not ETH3/SR9900');integer(cn['ifindex'],1,2**31-1);mac(cn['mac'])
    absolute(cn['device']);require(cn['device'].startswith('/sys/devices/') and '/1-1.4.1/' in cn['device'] and
        PurePosixPath(cn['device']).name=='1-1.4.1:1.0','USB device interface path')
    mgmt=policy['management'];keys(mgmt,'name driver mac addresses routes4 routes6')
    require(mgmt['name']=='eth0' and mgmt['driver']==MGMT_DRIVER and mgmt['mac']!=cn['mac'],'management alias')
    mac(mgmt['mac']);require(type(mgmt['addresses']) is list and mgmt['addresses'],'management addresses missing')
    require(any(a.get('family')=='inet' and a.get('local')=='192.168.2.141' and a.get('prefixlen')==24 for a in mgmt['addresses']),'management IP mismatch')
    require(type(mgmt['routes4']) is list and mgmt['routes4'] and type(mgmt['routes6']) is list,'management routes unpinned')
    artifact=policy['artifact'];keys(artifact,'path sha256 role interpreter');absolute(artifact['path']);digest(artifact['sha256'])
    require(artifact['interpreter']=='/lib/ld-linux-aarch64.so.1','unexpected dynamic loader')
    require(artifact['role']=='bounded-cn-frontend' and artifact['sha256']!=OLD_DEMO_SHA and PurePosixPath(artifact['path']).name not in DENIED_PROCESSES,'unbounded demo is not frontend')
    objects=policy['objects'];require(type(objects) is dict and set(objects)=={'libc.so.6','ld-linux-aarch64.so.1'},'only audited libc/loader closure supported')
    for name,obj in objects.items():
        keys(obj,'path sha256');absolute(obj['path']);digest(obj['sha256'])
    require(policy['limits']==LIMITS and all(type(v) is int for v in policy['limits'].values()),'budget changed')

def uses_device(value,name):
    if isinstance(value,dict):return value.get('dev')==name or any(uses_device(v,name) for v in value.values())
    if isinstance(value,list):return any(uses_device(v,name) for v in value)
    return False

def runtime_check(runtime,policy):
    keys(runtime,'artifact objects')
    for name,expected in [('artifact',policy['artifact'])]+list(policy['objects'].items()):
        item=runtime['artifact'] if name=='artifact' else runtime['objects'].get(name,{})
        keys(item,'path sha256 elf interpreter_target')
        require(item['path']==expected['path'] and item['sha256']==expected['sha256'],'runtime object SHA/path: '+name)
    require(set(runtime['objects'])==set(policy['objects']),'runtime closure differs')
    artifact=runtime['artifact']['elf'];loader=runtime['objects']['ld-linux-aarch64.so.1']
    require(artifact['interpreter']==policy['artifact']['interpreter'] and runtime['artifact']['interpreter_target']==loader['path'] and
            artifact['needed']==['libc.so.6'] and artifact['needs'],'unsupported executable closure')
    for name,item in [('artifact',runtime['artifact'])]+list(runtime['objects'].items()):
        elf=item['elf'];keys(elf,'interpreter needed needs definitions')
        require(not set(elf['needed'])-set(runtime['objects']),'unresolved dependency: '+name)
        require(not set(elf['needs'])-set(elf['needed']),'version provider outside NEEDED: '+name)
        if name!='artifact':require(elf['interpreter'] is None and item['interpreter_target'] is None,'nested interpreter')
        for provider,required in elf['needs'].items():
            available=runtime['objects'][provider]['elf']['definitions']
            require(set(required)<=set(available),'missing symbol versions: '+provider+' '+str(sorted(set(required)-set(available))))

def check(snapshot,policy,now_ns):
    """Return evidence-only PASS; data and policy are not authenticators/locks."""
    policy_check(policy);keys(snapshot,'schema frames');require(snapshot['schema']==SCHEMA,'snapshot version')
    require(type(snapshot['frames']) is list and len(snapshot['frames'])==2,'two fresh observations required')
    integer(now_ns)
    for frame in snapshot['frames']:
        keys(frame,'boot_id kernel machine euid cap_eff namespaces environment interface links addresses routes4 routes6 packet processes tc_ingress tc_egress management runtime start_ns end_ns')
        integer(frame['start_ns']);integer(frame['end_ns']);require(frame['start_ns']<=frame['end_ns']<=now_ns,'clock order')
        require(frame['boot_id']==policy['boot_id'] and frame['kernel']==policy['kernel'] and frame['machine']=='aarch64','host/boot mismatch')
        require(type(frame['euid']) is int and frame['euid']==0 and int(frame['cap_eff'],16)&(1<<13),'root/CAP_NET_RAW required')
        require(frame['namespaces']==policy['namespaces'],'namespace mismatch')
        require(type(frame['environment']) is dict and not any(k.startswith('LD_') for k in frame['environment']),'loader environment injection')
        require(frame['interface']==policy['interface'],'ETH3 identity changed')
        require(frame['management']==policy['management'],'management baseline changed')
        require(type(frame['links']) is list,'links not collected')
        cnrows=[x for x in frame['links'] if x.get('ifname')=='eth2'];require(len(cnrows)==1,'missing/duplicate CN interface')
        link=cnrows[0];require(link.get('ifindex')==policy['interface']['ifindex'] and link.get('address')==policy['interface']['mac'],'link identity')
        require(link.get('link_type')=='ether' and link.get('mtu')==1500 and link.get('operstate')=='UP' and
            set(link.get('flags',[]))=={'BROADCAST','MULTICAST','UP','LOWER_UP'},'link not clean/up/1500')
        require(not link.get('master') and not link.get('linkinfo') and not link.get('xdp') and not link.get('promiscuity',0),'bridge/bond/VLAN/XDP/promisc')
        for other in frame['links']:
            if other is link:continue
            require(other.get('link_index')!=link['ifindex'] and other.get('link')!='eth2' and other.get('master') not in ('eth2',link['ifindex']),'dependent/upper interface')
        require(frame['addresses']==[],'CN has IPv4/IPv6 address, including link-local')
        require(type(frame['routes4']) is list and type(frame['routes6']) is list and
            not uses_device(frame['routes4'],'eth2') and not uses_device(frame['routes6'],'eth2'),'CN has route in some table/nexthop')
        require(frame['tc_ingress']==[] and frame['tc_egress']==[],'tc filter attached or unobserved')
        require(not any(p['ifindex'] in (-1,0,link['ifindex']) for p in packet_table(frame['packet'])),'packet socket overlaps CN/all interfaces (even protocol0)')
        require(type(frame['processes']) is list and len(frame['processes'])<=4096,'process census missing/oversized')
        denied=DENIED_PROCESSES|{PurePosixPath(policy['artifact']['path']).name}
        for process in frame['processes']:
            keys(process,'pid start exe argv');integer(process['pid'],1,2**31-1);integer(process['start'],1)
            require(type(process['argv']) is list and all(type(x) is str for x in process['argv']),'bad argv')
            names={PurePosixPath(x).name for x in [process['exe']]+process['argv'][:2]}
            require(not names&denied,'conflicting process: '+str(process['pid']))
        runtime_check(frame['runtime'],policy)
    first,last=snapshot['frames']
    require(first['end_ns']<=last['start_ns'] and last['end_ns']-first['start_ns']<=MAX_SPAN_NS,'overlapping/slow census')
    require(now_ns-last['end_ns']<=MAX_AGE_NS,'stale snapshot')
    stable=lambda f:{k:v for k,v in f.items() if k not in ('start_ns','end_ns')}
    require(stable(first)==stable(last),'state changed between observations; no retry')
    return dict(schema=SCHEMA,preflight_pass=True,snapshot_sha256=sha(snapshot),policy_sha256=sha(policy),
        runtime_ready=False,execution_allowed=False,limit='Evidence only; advisory observations are not exclusive ownership or human approval.')
