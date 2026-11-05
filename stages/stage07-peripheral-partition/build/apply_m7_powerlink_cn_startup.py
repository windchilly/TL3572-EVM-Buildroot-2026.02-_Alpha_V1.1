"""P4e delivery activation, composed on the immutable P4d fresh-tree overlay."""
import hashlib,json,shutil
from pathlib import Path
from apply_m7_powerlink_cn_private import apply as private
from apply_m7_powerlink_cn_lifecycle import replace,function_span
STAGE=Path(__file__).resolve().parents[1]

def apply(tree):
    generated=private(tree)
    expected=json.loads((STAGE/'tests/powerlink-cn-p4d-20261105/native-final/build-report.json').read_text())['generated_sha256']
    if generated!=expected:raise ValueError('immutable P4d baseline drift')
    changes={}
    path='stack/src/common/m7_cn_lifecycle.c'
    text='#include <common/m7_cn_startup.h>\n'+(tree/path).read_text()
    text=replace(text,'unsigned claim, stop, attempted_slots;','unsigned claim, stop, ready, attempted_slots;')
    text=replace(text,'''    if (error!=kErrorOk)
        __atomic_compare_exchange_n(&life.stats.first_error,&clear,error,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);''',
        '''    if (error!=kErrorOk) {
        __atomic_compare_exchange_n(&life.stats.first_error,&clear,error,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
        STORE(life.ready,0);STORE(life.stop,1);
    }''')
    # Worker faults now record the shared first error. All reads must be atomic.
    text=text.replace('life.stats.first_error','LOAD(life.stats.first_error)')
    text=text.replace('&LOAD(life.stats.first_error)','&life.stats.first_error')
    text=text.replace('LOAD(LOAD(life.stats.first_error))','LOAD(life.stats.first_error)')
    text=replace(text,'    if (LOAD(life.stats.first_error) || m7_cn_stopping()) return kErrorInvalidOperation;',
                 '    if (LOAD(life.stats.first_error) || m7_cn_stopping()) return m7_cn_fail(kErrorInvalidOperation);')
    text=replace(text,'    life.stats.initialized=1;return kErrorOk;',
        '''    life.stats.initialized=1;
    error=m7_cn_edrv_activate();
    if (error!=kErrorOk || m7_cn_stopping()) {
        life.stats.initialized=0;
        return m7_cn_fail(error!=kErrorOk?error:kErrorInvalidOperation);
    }
    STORE(life.ready,1); /* release publishes complete user/kernel/OD/PDO state */
    return kErrorOk;''')
    text=replace(text,'life.stats.stop_attempted=1;STORE(life.stop,1);',
                 'life.stats.stop_attempted=1;STORE(life.ready,0);STORE(life.stop,1);')
    text=replace(text,'    if (stats && owner()) *stats=life.stats;',
        '''    if (stats && owner()) {
        stats->begun=life.stats.begun;stats->create_attempted=life.stats.create_attempted;
        stats->initialized=life.stats.initialized;stats->stop_attempted=life.stats.stop_attempted;
        stats->quiet=life.stats.quiet;stats->release_started=life.stats.release_started;
        stats->kernel_release_started=life.stats.kernel_release_started;stats->released=life.stats.released;
        stats->environment_exit_attempted=life.stats.environment_exit_attempted;
        stats->created=life.stats.created;stats->joined=life.stats.joined;
        stats->first_error=LOAD(life.stats.first_error);
    }''')
    text+='''
int m7_cn_ready(void) { return LOAD(life.ready) && !m7_cn_stopping(); }
int m7_cn_activation_allowed(void)
{
    return owner() && life.stats.initialized && !LOAD(life.ready) && !m7_cn_stopping();
}
int m7_cn_wait_ready(void)
{
    const struct timespec pause={0,1000000};
    while (!m7_cn_stopping()) {
        if (m7_cn_ready()) return 1;
        if (nanosleep(&pause,NULL) && errno!=EINTR) { m7_cn_fail(kErrorInvalidOperation);break; }
    }
    return 0;
}
'''
    changes[path]=text
    path='stack/src/common/m7_cn_timers.c'
    text='#include <common/m7_cn_startup.h>\n'+(tree/path).read_text()
    text=replace(text,'    return error;\n}', '    m7_cn_fail(error);return error;\n}')
    text=replace(text,'        pthread_mutex_lock(&timers->mutex);',
                 '        if (!m7_cn_wait_ready()) break;\n        pthread_mutex_lock(&timers->mutex);')
    text=replace(text,'if (due && !m7_cn_stopping())','if (due && m7_cn_ready())')
    changes[path]=text
    for kind,name in (('kernel','eventkcal'),('user','eventucal')):
        path='stack/src/'+kind+'/event/'+name+'-linux.c'
        text='#include <common/m7_cn_startup.h>\n#include <errno.h>\n'+(tree/path).read_text()
        text=replace(text,'        clock_gettime(CLOCK_MONOTONIC, &curTime);',
            '''        if (!m7_cn_wait_ready()) break;
        if (clock_gettime(CLOCK_MONOTONIC, &curTime)) { m7_cn_fail(kErrorInvalidOperation);break; }''')
        text=replace(text,'            if (m7_cn_stopping()) break;', '            if (!m7_cn_ready()) break;')
        text=replace(text,'        }\n    }\n\n\n    return 0;',
            '''        }
        else if (errno!=EINTR && errno!=ETIMEDOUT) { m7_cn_fail(kErrorInvalidOperation);break; }
    }


    return 0;''')
        # Keep upstream queue priority, but a failed dispatch is terminal.
        import re
        text,n=re.subn(r'(?m)^(\s*)('+name+r'_processEventCircbuf\([^;]+\));',
                       r'\1{ tOplkError ret=\2; if (ret!=kErrorOk) { m7_cn_fail(ret);break; } }',text)
        if n!=2:raise ValueError('event dispatch anchors drift: '+path)
        for sem in ('User','Kernel'):
            text=replace(text,'    sem_post(instance_l.sem'+sem+'Data);',
                '    if (sem_post(instance_l.sem'+sem+'Data)) m7_cn_fail(kErrorInvalidOperation);')
        changes[path]=text
    for kind,name in (('kernel','eventk'),('user','eventu')):
        path='stack/src/'+kind+'/event/'+name+'.c'
        text='#include <common/m7_cn_startup.h>\n'+(tree/path).read_text()
        text=replace(text,'    if (!m7_cn_timer_event_current(pEvent_p)) return kErrorOk;',
            '    if (!m7_cn_ready()) return kErrorInvalidOperation;\n    if (!m7_cn_timer_event_current(pEvent_p)) return kErrorOk;')
        changes[path]=text
    path='stack/src/user/api/generic.c';text='#include <common/m7_cn_startup.h>\n'+(tree/path).read_text()
    for function in ('oplk_execNmtCommand','oplk_process','oplk_postUserEvent'):
        start,end=function_span(text,function);code=text[start:end]
        # All three have this existing initialization check, after declarations.
        code=replace(code,'    if (!ctrlu_stackIsInitialized())',
                     '    if (!m7_cn_ready()) return kErrorInvalidOperation;\n    if (!ctrlu_stackIsInitialized())')
        text=text[:start]+code+text[end:]
    changes[path]=text
    path='stack/src/kernel/edrv/edrv-rawsock_linux.c'
    text='#include <common/m7_cn_startup.h>\n'+(STAGE/'source/powerlink/linux-cn/transport/edrv-m7-cn.c').read_text()
    text=replace(text,'int fd,ifindex,thread_created,stop;', 'int fd,ifindex,thread_created,stop,activation_attempted;')
    text=replace(text,'    STORE(g.stop,1);\n}',
        '    STORE(g.stop,1);\n    m7_cn_fail(kErrorInvalidOperation);\n}')
    text=replace(text,'    fault(reason);\n    (void)close_owned();',
                 '    m7_cn_fail(kErrorEdrvInit);\n    fault(reason);\n    (void)close_owned();')
    text=replace(text,'    if (!LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault)) return 0;',
                 '    if (!m7_cn_ready() || !LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault)) return 0;')
    text=replace(text,'    if (!LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault) || now>=g.deadline)',
                 '    if (!m7_cn_ready() || !LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault) || now>=g.deadline)')
    text=replace(text,'    while (!LOAD(g.stop)) {','    while (!LOAD(g.stop) && !m7_cn_stopping()) {')
    text=replace(text,'    ssize_t bytes;unsigned char* data;void* clear=NULL;tEdrvTxHandler callback;',
                 '    ssize_t bytes;unsigned char* data;void* clear=NULL;tEdrvTxHandler callback;\n    if (!m7_cn_ready()) return kErrorInvalidOperation;')
    text=replace(text,'(p.revents&POLLIN) && !LOAD(g.stop))',
                 '(p.revents&POLLIN) && !LOAD(g.stop) && m7_cn_ready())')
    text=replace(text,'        result=poll(&p,1,10);',
        '''        if (!m7_cn_ready()) {
            const struct timespec pause={0,1000000};
            if (nanosleep(&pause,NULL) && errno!=EINTR) { fault(F_IO);break; }
            continue;
        }
        result=poll(&p,1,10);''')
    text=replace(text,'    (void)close_owned();','    STORE(g.stats.joined,!g.thread_created);\n    (void)close_owned();')
    text=replace(text,'SOCK_CLOEXEC,htons(0x88ab))','SOCK_CLOEXEC,0)')
    text=replace(text,'    if (bind(g.fd,(struct sockaddr*)&addr,sizeof(addr))) return init_failed(F_BIND);','')
    text+='''
/* protocol=0 receives nothing (packet(7)); no pre-init packets can accumulate.
 * This sole bind commits admission only after the complete stack was validated.
 * Worker dispatch remains gated until the owner publishes ready afterwards. */
tOplkError m7_cn_edrv_activate(void)
{
    struct sockaddr_ll addr={0};
    if (!m7_cn_activation_allowed() || !pthread_equal(g.owner,pthread_self()) ||
        !LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault) || g.activation_attempted)
        return kErrorInvalidOperation;
    g.activation_attempted=1;
    if (now_ns()>=g.deadline || LOAD(g.stats.clock_failed)) { fault(F_BUDGET);return kErrorInvalidOperation; }
    addr.sll_family=AF_PACKET;addr.sll_protocol=htons(0x88ab);addr.sll_ifindex=g.ifindex;
    if (bind(g.fd,(struct sockaddr*)&addr,sizeof(addr))) { fault(F_BIND);return kErrorInvalidOperation; }
    return kErrorOk;
}
'''
    changes[path]=text
    for source,target in (('source/powerlink/linux-cn/startup/m7_cn_startup.h','stack/include/common/m7_cn_startup.h'),
                          ('source/powerlink/linux-cn/transport/m7_cn_edrv.h','stack/src/kernel/edrv/m7_cn_edrv.h')):
        shutil.copyfile(STAGE/source,tree/target);generated[target]=hashlib.sha256((tree/target).read_bytes()).hexdigest()
    for path,text in changes.items():
        (tree/path).write_text(text,encoding='utf-8',newline='\n')
        generated[path]=hashlib.sha256((tree/path).read_bytes()).hexdigest()
    return generated
