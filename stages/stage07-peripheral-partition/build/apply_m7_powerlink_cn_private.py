"""P4d process-private queues and generation timers, on immutable P4c sources."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
from apply_m7_powerlink_cn_lifecycle import apply as lifecycle,body,replace,function_span
STAGE=Path(__file__).resolve().parents[1]
PRIVATE=STAGE/'source/powerlink/linux-cn/private'
RAW=('stack/src/common/circbuf/circbuffer.c','stack/src/kernel/event/eventk.c','stack/src/user/event/eventu.c',
     'stack/src/kernel/event/eventkcalintf-circbuf.c','stack/src/user/event/eventucalintf-circbuf.c','stack/src/arch/linux/target-linux.c',
     'stack/src/arch/linux/target-mutex.c','stack/src/user/pdo/pdou.c')

def apply(tree):
    lock=json.loads((STAGE/'source/powerlink/upstream.lock.json').read_text())
    with tarfile.open(STAGE/'source/powerlink'/lock['archive'],'r:gz') as archive:
        for name in RAW:
            original=archive.extractfile(lock['archive_prefix']+'/'+name).read().decode().replace('\r\n','\n')
            if (tree/name).read_text()!=original:raise ValueError('private overlay input drift: '+name)
    generated=lifecycle(tree)
    expected=json.loads((STAGE/'tests/powerlink-cn-p4c-20261105/native-final/build-report.json').read_text())['generated_sha256']
    if generated!=expected:raise ValueError('immutable P4c baseline drift')
    changes={}
    for kind in ('kernel','user'):
        prefix='eventkcal' if kind=='kernel' else 'eventucal'
        path='stack/src/'+kind+'/event/'+prefix+'-linux.c'
        text='#include <common/m7_cn_private.h>\n'+(tree/path).read_text()
        begin=text.index('    sem_unlink(') if kind=='kernel' else text.index('    if ((instance_l.semUserData = sem_open(')
        end=text.index('    if ('+prefix+'_initQueueCircbuf',begin)
        init='m7_cn_event_sems_init' if kind=='kernel' else 'm7_cn_event_sems_attach'
        text=text[:begin]+('    if ('+init+'() != kErrorOk) goto Exit;\n'
                          '    instance_l.semUserData = m7_cn_event_sem(0);\n'
                          '    instance_l.semKernelData = m7_cn_event_sem(1);\n\n')+text[end:]
        old=('        if (sem_close(instance_l.semUserData)) return m7_cn_fail(kErrorInvalidOperation);\n'
             '        if (sem_close(instance_l.semKernelData)) return m7_cn_fail(kErrorInvalidOperation);')
        exit='m7_cn_event_sems_exit' if kind=='kernel' else 'm7_cn_event_sems_detach'
        text=replace(text,old,'        { tOplkError ret = '+exit+'(); if (ret != kErrorOk) return m7_cn_fail(ret); }')
        if kind=='kernel':text=replace(text,'        sem_unlink("/semUserEvent");\n        sem_unlink("/semKernelEvent");','')
        text=replace(text,'clock_gettime(CLOCK_REALTIME, &curTime);','clock_gettime(CLOCK_MONOTONIC, &curTime);')
        semaphore='semKernelData' if kind=='kernel' else 'semUserData'
        text=replace(text,'sem_timedwait(pInstance->'+semaphore+', &timeout)',
                     'sem_clockwait(pInstance->'+semaphore+', CLOCK_MONOTONIC, &timeout)')
        changes[path]=text
    for path in ('stack/src/kernel/event/eventk.c','stack/src/user/event/eventu.c'):
        text='#include <common/m7_cn_private.h>\n'+(tree/path).read_text()
        # Only the dispatch function has this switch; validation never dereferences
        # timer arguments' application-owned pointers, just the generation handle.
        start,end=function_span(text,'eventk_process' if '/kernel/' in path else 'eventu_process')
        code=replace(text[start:end],'    switch (pEvent_p->eventSink)',
                     '    if (!m7_cn_timer_event_current(pEvent_p)) return kErrorOk;\n\n    switch (pEvent_p->eventSink)')
        text=text[:start]+code+text[end:]
        changes[path]=text
    for path in ('stack/src/kernel/event/eventkcalintf-circbuf.c','stack/src/user/event/eventucalintf-circbuf.c'):
        text=(tree/path).read_text();count=text.count('eventQueue_p > kEventQueueNum')
        if count!=(7 if '/kernel/' in path else 6):raise ValueError('event queue index checks drift: '+path+' '+str(count))
        changes[path]=text.replace('eventQueue_p > kEventQueueNum','(unsigned)eventQueue_p >= (unsigned)kEventQueueNum')
    path='stack/src/common/circbuf/circbuffer.c';text=(tree/path).read_text()
    text=replace(text,'    circbuf_unlock(pInstance_p);\n    if (pInstance_p->pfnSigCb != NULL)',
                 '    circbuf_unlock(pInstance_p);\n\n    if (pInstance_p->pfnSigCb != NULL)')
    text=replace(text,'''    circbuf_unlock(pInstance_p);

    if (pInstance_p->pfnSigCb != NULL)
    {
        pInstance_p->pfnSigCb();
    }''','''    {
        VOIDFUNCPTR signal = pInstance_p->pfnSigCb;
        circbuf_unlock(pInstance_p);
        if (signal != NULL) signal();
    }''',count=2)
    text=replace(text,'    return pHeader->dataCount;','''    {
        UINT32 count;
        circbuf_lock((tCircBufInstance*)pInstance_p);
        count = pHeader->dataCount;
        circbuf_unlock((tCircBufInstance*)pInstance_p);
        return count;
    }''')
    text=replace(text,'    pInstance_p->pfnSigCb = pfnSigCb_p;','''    circbuf_lock(pInstance_p);
    pInstance_p->pfnSigCb = pfnSigCb_p;
    circbuf_unlock(pInstance_p);''')
    changes[path]=text
    path='stack/src/arch/linux/target-linux.c';text=(tree/path).read_text()
    text=body(text,'target_init','    return kErrorOk; /* No timer signals or global ftrace changes. */')
    changes[path]=body(text,'target_cleanup','    return kErrorOk;')
    path='stack/src/arch/linux/target-mutex.c';text='#include <common/m7_cn_lifecycle.h>\n'+(tree/path).read_text()
    text=replace(text,'        sem_destroy(pLockSem);','        if (sem_destroy(pLockSem)) { m7_cn_fail(kErrorInvalidOperation); return; }')
    changes[path]=text
    path='stack/src/user/pdo/pdou.c';text='#include <common/m7_cn_lifecycle.h>\n'+(tree/path).read_text()
    start,end=function_span(text,'pdou_exit');code=text[start:end]
    code=replace(code,'        target_lockMutex(pdouInstance_g.lockMutex);',
                 '        ret = target_lockMutex(pdouInstance_g.lockMutex);\n        if (ret != kErrorOk) return m7_cn_fail(ret);')
    code=replace(code,'        target_destroyMutex(pdouInstance_g.lockMutex);',
                 '''        target_destroyMutex(pdouInstance_g.lockMutex);
        {
            M7CnLifecycleStats stats = {0};
            m7_cn_lifecycle_stats(&stats);
            if (stats.first_error != kErrorOk) return stats.first_error;
        }''')
    changes[path]=text[:start]+code+text[end:]
    path='stack/src/common/m7_cn_lifecycle.c';text=(tree/path).read_text()
    text='#include <common/m7_cn_private.h>\n'+text
    text=replace(text,'    life.stats.initialized=1;return kErrorOk;',
                 '    if (m7_cn_timers_fault()!=kErrorOk) return m7_cn_fail(m7_cn_timers_fault());\n    life.stats.initialized=1;return kErrorOk;')
    text=replace(text,'    tOplkError result=m7_cn_quiesce();',
                 '    tOplkError result=m7_cn_quiesce();\n    if (result==kErrorOk && m7_cn_timers_fault()!=kErrorOk) result=m7_cn_fail(m7_cn_timers_fault());')
    changes[path]=text
    path='stack/proj/linux/liboplkcn/CMakeLists.txt';text=(tree/path).read_text()
    text=replace(text,'ADD_LIBRARY(${LIB_NAME} ${LIB_TYPE} ${LIB_SOURCES})',
        '''LIST(REMOVE_ITEM LIB_SOURCES ${KERNEL_SOURCE_DIR}/timer/hrestimer-posix.c ${USER_SOURCE_DIR}/timer/timer-linuxuser.c)
LIST(APPEND LIB_SOURCES ${COMMON_SOURCE_DIR}/m7_cn_private.c ${COMMON_SOURCE_DIR}/m7_cn_timers.c)
ADD_LIBRARY(${LIB_NAME} ${LIB_TYPE} ${LIB_SOURCES})''')
    changes[path]=text
    for relative,text in changes.items():(tree/relative).write_text(text,encoding='utf-8',newline='\n')
    for source,target in (('m7_cn_private.h','stack/include/common/m7_cn_private.h'),
                          ('m7_cn_private.c','stack/src/common/m7_cn_private.c'),
                          ('m7_cn_timers.c','stack/src/common/m7_cn_timers.c'),
                          ('circbuf-m7-private.c','stack/src/common/circbuf/circbuf-posixshm.c')):
        shutil.copyfile(PRIVATE/source,tree/target);generated[target]=hashlib.sha256((tree/target).read_bytes()).hexdigest()
    generated.update({p:hashlib.sha256((tree/p).read_bytes()).hexdigest() for p in changes})
    return generated
