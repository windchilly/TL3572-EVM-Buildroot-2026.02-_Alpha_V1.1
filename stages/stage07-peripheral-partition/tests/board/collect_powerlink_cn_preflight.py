#!/usr/bin/env python3
"""P4f READ-ONLY collector/replay. Never arms/starts CN, even after PASS.
--replay reads saved JSON only. Without it, collect locally twice and print JSON;
no remote access, network socket, interface write, permanent marker or candidate
execution (including --help/ldd/loader --list). This is NOT the runtime frontend.
"""
import argparse,hashlib,json,os,platform,stat,subprocess,time
from pathlib import Path
from powerlink_cn_preflight import (SCHEMA,MAX_SPAN_NS,absolute,check,elf_report,
    policy_check,require,unique_json,uses_device)

def read(path,limit=262144):
    with Path(path).open('rb') as file:data=file.read(limit+1)
    require(len(data)<=limit,'oversized read: '+str(path));return data.decode('utf-8')

def command(argv):
    # Only internal constant read-only commands; no shell, no candidate argv.
    allowed={('/sbin/ip','-j','-details','link','show'),
        ('/sbin/ip','-j','address','show','dev','eth2'),('/sbin/ip','-j','address','show','dev','eth0'),
        ('/sbin/ip','-j','-4','route','show','table','all'),('/sbin/ip','-j','-6','route','show','table','all'),
        ('/sbin/tc','-j','filter','show','dev','eth2','ingress'),('/sbin/tc','-j','filter','show','dev','eth2','egress')}
    require(tuple(argv) in allowed,'command not read-only allowlisted')
    result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2,
        env={'LC_ALL':'C','LANG':'C','PATH':'/usr/sbin:/usr/bin:/sbin:/bin'},check=True)
    require(len(result.stdout)<=2*1024*1024 and not result.stderr,'command warning/oversized output')
    return result.stdout.decode('utf-8')

def trusted_file(path,expected):
    """Read/hash the same regular file descriptor; no ELF execution."""
    absolute(path)
    # Trusted root-owned ancestors, no group/other write or symlink aliases.
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        parts=Path(path).parts[1:]
        for part in parts[:-1]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=nxt;meta=os.fstat(fd)
            require(meta.st_uid==0 and (not meta.st_mode&0o022 or meta.st_mode&stat.S_ISVTX),'unsafe runtime ancestor')
        obj=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
        try:
            before=os.fstat(obj)
            require(stat.S_ISREG(before.st_mode) and before.st_uid==0 and before.st_nlink==1 and not before.st_mode&0o022 and 0<before.st_size<=32*1024*1024,'unsafe runtime object')
            digest=hashlib.sha256()
            with os.fdopen(os.dup(obj),'rb') as stream:
                for block in iter(lambda:stream.read(65536),b''):digest.update(block)
            require(digest.hexdigest()==expected,'runtime object hash mismatch')
            # Pass only the already-open descriptor, so replacement paths cannot
            # make readelf inspect a different inode. Parent keeps it open.
            def elf(flag):
                result=subprocess.run(['/usr/bin/readelf','--wide',flag,'/proc/self/fd/'+str(obj)],
                    pass_fds=(obj,),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2,
                    env={'LC_ALL':'C','LANG':'C','PATH':'/usr/bin'},check=True)
                require(not result.stderr and len(result.stdout)<=2*1024*1024,'readelf warning/size')
                return result.stdout.decode()
            report=elf_report(elf('-h'),elf('-l'),elf('-d'),elf('-V'))
            after=os.fstat(obj)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'object changed while inspecting')
            target=str(Path(report['interpreter']).resolve(strict=True)) if report['interpreter'] else None
            return dict(path=path,sha256=digest.hexdigest(),elf=report,interpreter_target=target)
        finally:os.close(obj)
    finally:os.close(fd)

def processes():
    root=Path('/proc');pids=sorted(int(p.name) for p in root.iterdir() if p.name.isdecimal())
    require(len(pids)<=4096,'too many processes');out=[]
    for pid in pids:
        entry=root/str(pid);before=read(entry/'stat',8192)
        # comm may itself contain spaces and parentheses; field22=starttime.
        start=int(before[before.rfind(')')+2:].split()[19])
        argv=read(entry/'cmdline',65536).rstrip('\0').split('\0')
        try:exe=os.readlink(entry/'exe')
        except FileNotFoundError:
            require(argv==[''],'vanished/hidden process');exe='[kernel]';argv=[]
        after=read(entry/'stat',8192)
        require(int(after[after.rfind(')')+2:].split()[19])==start,'PID reused during observation')
        out.append(dict(pid=pid,start=start,exe=exe,argv=argv))
    require(pids==sorted(int(p.name) for p in root.iterdir() if p.name.isdecimal()),'process census changed; no retry')
    return out

def collect_frame(policy):
    start=time.monotonic_ns()
    def net(*args):return unique_json(command(['/sbin/ip','-j',*args]))
    def ns(pid):return {kind:os.readlink('/proc/'+pid+'/ns/'+kind) for kind in ('net','pid','user')}
    own=ns('self');require(own==ns('1'),'not initial visible namespaces')
    # Root in a PID-restricted/container namespace is not proven host root.
    # Pinned kernel/sysfs/ns identity remains mandatory; future frontend also
    # needs an independently reviewed host deployment and exclusive context.
    links=net('-details','link','show');addresses=net('address','show','dev','eth2')
    require(len(addresses)==1 and addresses[0].get('ifname')=='eth2','ambiguous address output')
    routes4=net('-4','route','show','table','all');routes6=net('-6','route','show','table','all')
    management=net('address','show','dev','eth0');require(len(management)==1,'management port missing')
    def identity(name):
        root=Path('/sys/class/net')/name
        return dict(name=name,ifindex=int(read(root/'ifindex',32)),mac=read(root/'address',32).strip(),
            driver=str((root/'device/driver').resolve(strict=True)),device=str((root/'device').resolve(strict=True)))
    cn=identity('eth2');mgmt=identity('eth0')
    status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in read('/proc/self/status').splitlines() if ':' in line}
    runtime=dict(artifact=trusted_file(policy['artifact']['path'],policy['artifact']['sha256']),objects={
        name:trusted_file(obj['path'],obj['sha256']) for name,obj in policy['objects'].items()})
    frame=dict(boot_id=read('/proc/sys/kernel/random/boot_id',64).strip(),kernel=platform.release(),machine=platform.machine(),
        euid=os.geteuid(),cap_eff=status['CapEff'],namespaces=own,environment={k:v for k,v in os.environ.items() if k.startswith('LD_')},
        interface=cn,links=links,addresses=addresses[0].get('addr_info'),routes4=routes4,routes6=routes6,
        packet=read('/proc/net/packet'),processes=processes(),
        tc_ingress=unique_json(command(['/sbin/tc','-j','filter','show','dev','eth2','ingress'])),
        tc_egress=unique_json(command(['/sbin/tc','-j','filter','show','dev','eth2','egress'])),
        management=dict(name='eth0',driver=mgmt['driver'],mac=mgmt['mac'],addresses=management[0].get('addr_info'),
            routes4=[r for r in routes4 if uses_device(r,'eth0')],routes6=[r for r in routes6 if uses_device(r,'eth0')]),
        runtime=runtime,start_ns=start,end_ns=time.monotonic_ns())
    require(frame['end_ns']-start<=MAX_SPAN_NS,'slow read-only collection');return frame

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--replay',type=Path);parser.add_argument('--now-ns',type=int)
    args=parser.parse_args();policy=unique_json(read(args.policy,4*1024*1024));policy_check(policy)
    if args.replay:
        require(args.now_ns is not None,'offline replay requires explicit recorded monotonic time')
        snapshot=unique_json(read(args.replay,4*1024*1024));now=args.now_ns;mode='offline-replay'
    else:
        require(args.now_ns is None and platform.system()=='Linux' and os.geteuid()==0,'local Linux root collection only')
        require(not any(k.startswith('LD_') for k in os.environ),'LD_ environment rejected before subprocess')
        snapshot=dict(schema=SCHEMA,frames=[collect_frame(policy),collect_frame(policy)]);now=time.monotonic_ns();mode='local-read-only'
    result=check(snapshot,policy,now)
    print(json.dumps(dict(mode=mode,result=result,snapshot=snapshot),indent=2,sort_keys=True))
if __name__=='__main__':main()
