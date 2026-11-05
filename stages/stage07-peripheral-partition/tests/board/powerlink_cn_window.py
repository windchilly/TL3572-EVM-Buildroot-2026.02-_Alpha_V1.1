"""P4f Linux-only durable one-shot storage component; NO executable frontend.
Requires a pre-existing root-owned secure common directory. A successful claim
keeps a process lock and permanent HOLD; even close never removes evidence.
No cleanup/recovery API is supplied until real quiescence proof is integrated.
Filesystem fsync support is required, but power-loss/storage guarantees and
fresh human authorization must be validated by the future caller, not JSON.
"""
import os,stat,sys,time
from pathlib import Path
from powerlink_cn_preflight import absolute,canonical,digest,integer,keys,require,uuid_text

def record_check(record,boot,now):
    keys(record,'schema window_id boot_id created_ns expires_ns policy_sha256 snapshot_sha256 artifact_sha256')
    require(record['schema']=='m7-cn-window-v1','window schema');uuid_text(record['window_id']);uuid_text(record['boot_id'])
    integer(record['created_ns']);integer(record['expires_ns']);integer(now)
    require(record['boot_id']==boot and record['created_ns']<=now<=record['expires_ns'] and
            0<record['expires_ns']-record['created_ns']<=2_000_000_000,'window boot/time invalid')
    for name in ('policy_sha256','snapshot_sha256','artifact_sha256'):digest(record[name])

def secure_directory(path):
    absolute(str(path));fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        parts=Path(path).parts[1:];require(bool(parts),'broad root directory rejected')
        for index,part in enumerate(parts):
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=nxt;meta=os.fstat(fd)
            require(meta.st_uid==0,'window directory not root owned')
            if index==len(parts)-1:require(stat.S_IMODE(meta.st_mode)==0o700,'window directory must be 0700')
            else:require(not meta.st_mode&0o022 or meta.st_mode&stat.S_ISVTX,'writable nonsticky ancestor')
        return fd
    except BaseException:os.close(fd);raise

def write_once(directory,name,data):
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
    try:
        require(os.write(fd,data)==len(data),'short permanent marker write; retain file')
        os.fsync(fd);os.fsync(directory)
    finally:os.close(fd) # Never unlink, truncate, rewrite or retry ambiguous close.

class Window:
    def __init__(self,directory,lock):self.directory=directory;self.lock=lock
    def close(self):
        # Only releases THIS process's descriptors, not HOLD or ATTEMPTED.
        if self.lock is not None:
            fd=self.lock;self.lock=None;os.close(fd)
        if self.directory is not None:
            fd=self.directory;self.directory=None;os.close(fd)

def claim(path,record):
    require(sys.platform.startswith('linux') and os.geteuid()==0,'Linux root window only')
    require(not any(k.startswith('LD_') for k in os.environ),'LD_ environment rejected')
    record=dict(record) # Caller cannot change marker path/content during fsync.
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    record_check(record,boot,time.monotonic_ns())
    import fcntl
    directory=secure_directory(path);lock=None
    try:
        lock=os.open('LOCK',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
        meta=os.fstat(lock)
        require(stat.S_ISREG(meta.st_mode) and meta.st_uid==0 and meta.st_nlink==1 and
                stat.S_IMODE(meta.st_mode)==0o600 and meta.st_size==0,'unsafe common lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Any HOLD type, including a broken symlink or torn write, blocks all
        # later window ids. No dependence on PID liveness, reboot or exit code.
        try:os.stat('HOLD',dir_fd=directory,follow_symlinks=False)
        except FileNotFoundError:pass
        else:raise FileExistsError('previous window HOLD remains; no recovery/retry authorized')
        data=canonical(record)+b'\n'
        write_once(directory,'ATTEMPTED-'+record['window_id'],data)
        write_once(directory,'HOLD',data)
        record_check(record,boot,time.monotonic_ns()) # Expired during fsync: retain all markers.
        return Window(directory,lock)
    except BaseException:
        if lock is not None:os.close(lock)
        os.close(directory);raise
