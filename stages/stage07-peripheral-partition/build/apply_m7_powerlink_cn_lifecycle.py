"""P4c Linux-CN-only overlay on the pinned archive, never the UP2 port.

Generate a new build tree with tracked callback workers and two-phase teardown.
Exact anchors and the pinned input digest reject drift; not a generic C rewriter.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil

STAGE = Path(__file__).resolve().parents[1]
OVERLAY = STAGE / 'source/powerlink/linux-cn/lifecycle'


def function_span(text, name):
    match = re.search(r'^(?:static )?(?:tOplkError|void|int)\s+' + re.escape(name) + r'\([^;]*?\)\s*\{', text, re.M)
    if not match:
        raise ValueError('missing function ' + name)
    start = text.index('{', match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return start + 1, end - 1


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('unexpected lifecycle anchor: ' + old[:100])
    return text.replace(old, new)


def body(text, name, content):
    start, end = function_span(text, name)
    return text[:start] + '\n' + content.strip('\n') + '\n' + text[end:]


def apply(tree):
    # prepare() already authenticates every archive byte/commit/file count. This
    # additional per-file map enforces exactly the expected pre-overlay sources.
    lock = json.loads((OVERLAY / 'upstream-files.json').read_text())
    originals = {}
    for relative, expected in lock.items():
        path = tree / relative
        raw = path.read_bytes()
        normalized = raw.decode().replace('\r\n', '\n')
        if hashlib.sha256(normalized.encode()).hexdigest() != expected:
            raise ValueError('unexpected pinned Linux CN input: ' + relative)
        originals[relative] = normalized
    changed = {}
    def edit(relative, transform):
        changed[relative] = transform(originals[relative])

    def generic(text):
        text = '#include <common/m7_cn_lifecycle.h>\n' + text
        text = body(text, 'oplk_initialize', '''
    tOplkError ret = m7_cn_lifecycle_begin();
    if (ret != kErrorOk) return ret; /* unarmed: before target/IPC/threads */
    ret = target_init();
    if (ret != kErrorOk) return m7_cn_fail(ret);
    ret = ctrlu_init();
    if (ret != kErrorOk) return m7_cn_fail(ret);
    if (memmap_init() != kMemMapOk) return m7_cn_fail(kErrorNoResource);
    return kErrorOk;
''')
        text = body(text, 'oplk_create', '''
    tOplkError ret = m7_cn_create_begin();
    if (ret != kErrorOk) return ret;
    fStackInitialized_l = TRUE; /* pending includes partial initialization */
    ret = ctrlu_checkKernelStackInfo();
    if (ret == kErrorOk) ret = ctrlu_initStack(pInitParam_p);
    return m7_cn_init_result(ret);
''')
        text = body(text, 'oplk_destroy', '''
    tOplkError ret;
    if (m7_cn_released()) return kErrorOk;
    ret = ctrlu_shutdownStack();
    if (ret == kErrorOk) fStackInitialized_l = FALSE;
    return ret;
''')
        return body(text, 'oplk_exit', '''
    /* No cleanup on partial init, failed join or partially failed release. */
    if (!m7_cn_released())
    {
        if (oplk_destroy() != kErrorOk) return;
    }
    if (m7_cn_environment_exit_begin() != kErrorOk) return;
    ctrlu_exit();
    memmap_shutdown();
    m7_cn_fail(target_cleanup());
''')
    edit('stack/src/user/api/generic.c', generic)

    def ctrlu(text):
        text = '#include <common/m7_cn_lifecycle.h>\n' + text
        start, end = function_span(text, 'ctrlu_shutdownStack')
        code = text[start:end]
        code = replace(code, '    ctrlInstance_l.fInitialized = FALSE;', '''    if (m7_cn_released()) return kErrorOk;
    ret = m7_cn_release_begin();
    if (ret != kErrorOk) return ret;
    ctrlInstance_l.fInitialized = FALSE;''')
        # Preserve the first failing release and never run subsequent destructors.
        code, count = re.subn(r'(if \(ret != kErrorOk\)\n    \{)([^{}]*)(\n    \})',
                             r'\1\2\n        return m7_cn_fail(ret);\3', code)
        if count != 17:
            raise ValueError('unexpected user shutdown error checks: ' + str(count))
        code = replace(code, '    ret = obdal_exit();', '''    if ((tOplkError)retVal != kErrorOk) return m7_cn_fail((tOplkError)retVal);
    ret = obdal_exit();''')
        code = replace(code, '    return ret;', '    return m7_cn_release_finish();')
        return text[:start] + code + text[end:]
    edit('stack/src/user/ctrl/ctrlu.c', ctrlu)

    def ctrlk(text):
        text = '#include <common/m7_cn_lifecycle.h>\n' + text
        text = body(text, 'shutdownStack', '''
    tOplkError ret = m7_cn_kernel_release_begin();
    if (ret != kErrorOk) return ret;
#define M7_EXIT(call) do { ret = (call); if (ret != kErrorOk) return m7_cn_fail(ret); } while (0)
    M7_EXIT(pdok_exit());
    M7_EXIT(nmtk_exit());
    M7_EXIT(dllk_exit());
    M7_EXIT(hrestimer_exit());
    M7_EXIT(dllkcal_exit());
    M7_EXIT(eventk_exit());
    timesynck_exit();
    M7_EXIT(errhndk_exit());
#undef M7_EXIT
    return kErrorOk;
''')
        text = replace(text, 'status = kCtrlStatusReady;\n            fExit = FALSE;',
                       'status = (retVal == kErrorOk) ? kCtrlStatusReady : kCtrlStatusUnchanged;\n            fExit = FALSE;')
        text = replace(text, 'status = kCtrlStatusRunning;\n            fExit = FALSE;',
                       'status = (retVal == kErrorOk) ? kCtrlStatusRunning : kCtrlStatusUnchanged;\n            fExit = FALSE;')
        text = replace(text, '*pRet_p = (UINT16)retVal;\n            status = kCtrlStatusUnavailable;\n            fExit = TRUE;',
                       '*pRet_p = (UINT16)retVal;\n            status = (retVal == kErrorOk) ? kCtrlStatusUnavailable : kCtrlStatusUnchanged;\n            fExit = (retVal == kErrorOk);')
        return text
    edit('stack/src/kernel/ctrl/ctrlk.c', ctrlk)

    # These four are the only non-EDRV pthread_create sites selected by liboplkcn.
    # They inherit blocked timer signals from target_init. No SCHED_FIFO/RR writes.
    def worker(text, slot, name):
        text = '#include <common/m7_cn_lifecycle.h>\n' + text
        text = replace(text, 'pthread_create(', 'm7_cn_thread_create(')
        if slot == 'M7_CN_TIMERU':
            text = replace(text, 'm7_cn_thread_create(&timeruInstance_g.processThread,\n                            NULL,',
                           'm7_cn_thread_create(M7_CN_TIMERU, &timeruInstance_g.processThread,')
        elif slot == 'M7_CN_HRES':
            text = replace(text, 'm7_cn_thread_create(&hresTimerInstance_l.threadId, NULL,',
                           'm7_cn_thread_create(M7_CN_HRES, &hresTimerInstance_l.threadId,')
        else:
            text = replace(text, 'm7_cn_thread_create(&instance_l.threadId, NULL,',
                           'm7_cn_thread_create(' + slot + ', &instance_l.threadId,')
        # Remove complete scheduling blocks, including hres's unsafe cancel path.
        start = text.index('    schedParam.sched_priority = ')
        end = text.index('\n#if (defined(__GLIBC__)', start)
        text = text[:start] + text[end:]
        text = re.sub(r'^    struct sched_param\s+schedParam;\n', '', text, flags=re.M)
        if name in ('eventkcal', 'eventucal'):
            # Partial init deliberately retains queues/handles; never close a
            # partially initialized semaphore or detach a possibly live queue.
            start = text.index('\nExit:\n')
            end = text.index('    return kErrorNoResource;', start)
            text = text[:start] + '\nExit:\n' + text[end:]
            start, end = function_span(text, name + '_exit')
            code = text[start:end]
            code = replace(code, '    UINT    i = 0;', '    if (!m7_cn_can_release()) return kErrorInvalidOperation;')
            start_wait = code.index('        instance_l.fStopThread = TRUE;')
            end_wait = code.index('        ' + name + '_exitQueueCircbuf', start_wait)
            code = code[:start_wait] + code[end_wait:]
            code = re.sub(r'        (' + name + r'_exitQueueCircbuf\([^;]+\));',
                          r'        { tOplkError ret = \1; if (ret != kErrorOk) return m7_cn_fail(ret); }', code)
            # Resource-close failures stop teardown. No ambiguous second close.
            code = code.replace('        sem_close(instance_l.semUserData);',
                                '        if (sem_close(instance_l.semUserData)) return m7_cn_fail(kErrorInvalidOperation);')
            code = code.replace('        sem_close(instance_l.semKernelData);',
                                '        if (sem_close(instance_l.semKernelData)) return m7_cn_fail(kErrorInvalidOperation);')
            text = text[:start] + code + text[end:]
            text = replace(text, 'while (!pInstance->fStopThread)', 'while (!m7_cn_stopping())')
            text = replace(text, '    pInstance->fStopThread = FALSE;', '')
            text = replace(text, '            /* first handle', '            if (m7_cn_stopping()) break;\n            /* first handle')
        else:
            text = replace(text, '    while (1)', '    while (!m7_cn_stopping())')
            text = replace(text, '    siginfo_t', '    const struct timespec waitBudget = {0, 10000000};\n    siginfo_t')
            text = replace(text, 'sigwaitinfo(&awaitedSignal, &signalInfo)',
                           'sigtimedwait(&awaitedSignal, &signalInfo, &waitBudget)')
            anchor = '            pTimerInfo =' if name == 'hrestimer' else '            pTimer ='
            text = replace(text, anchor, '            if (m7_cn_stopping()) break;\n' + anchor)
            start, end = function_span(text, name + '_exit')
            code = text[start:end]
            if name == 'hrestimer':
                code = replace(code, '    for (index', '    if (!m7_cn_can_release()) return kErrorInvalidOperation;\n\n    for (index')
                code = replace(code, '        timer_delete(pTimerInfo->timer);',
                               '        if (timer_delete(pTimerInfo->timer)) return m7_cn_fail(kErrorInvalidOperation);')
                begin = code.index('    /* send exit signal')
                finish = code.index('    return ret;', begin)
                code = code[:begin] + code[finish:]
            else:
                begin = code.index('    /* Check if the processThread exist */')
                finish = code.index('    /* free up timer list */', begin)
                code = code[:begin] + '    if (!m7_cn_can_release()) return kErrorInvalidOperation;\n\n' + code[finish:]
                code = replace(code, '        removeTimer(pTimer);',
                               '        if (timer_delete(pTimer->timer)) return m7_cn_fail(kErrorInvalidOperation);\n        removeTimer(pTimer);')
                code = replace(code, '    pthread_mutex_destroy(&timeruInstance_g.mutex);',
                               '    if (pthread_mutex_destroy(&timeruInstance_g.mutex)) return m7_cn_fail(kErrorInvalidOperation);')
            text = text[:start] + code + text[end:]
        return text
    for relative, slot, name in (
        ('stack/src/kernel/event/eventkcal-linux.c', 'M7_CN_EVENTK', 'eventkcal'),
        ('stack/src/user/event/eventucal-linux.c', 'M7_CN_EVENTU', 'eventucal'),
        ('stack/src/kernel/timer/hrestimer-posix.c', 'M7_CN_HRES', 'hrestimer'),
        ('stack/src/user/timer/timer-linuxuser.c', 'M7_CN_TIMERU', 'timeru')):
        edit(relative, lambda text, slot=slot, name=name: worker(text, slot, name))

    def config(text):
        text = replace(text, '#define CONFIG_TIMER_USE_HIGHRES                    TRUE', '''#define CONFIG_TIMER_USE_HIGHRES                    TRUE
/* Fixed P4c profile; do not silently extend the two-phase stop to other builds. */
#if defined(CONFIG_INCLUDE_NMT_MN) || defined(CONFIG_INCLUDE_CFM) || defined(CONFIG_INCLUDE_VETH) || defined(CONFIG_INCLUDE_LEDK) || defined(CONFIG_INCLUDE_STORE_RESTORE)
#error P4c lifecycle supports only the fixed Linux software CN profile
#endif
#if CONFIG_DLL_PROCESS_SYNC != DLL_PROCESS_SYNC_ON_SOC
#error P4c lifecycle requires SOC sync (no independent synctimer)
#endif''')
        return text
    edit('stack/proj/linux/liboplkcn/oplkcfg.h', config)
    edit('stack/proj/linux/liboplkcn/CMakeLists.txt', lambda text: replace(text, '     ${USER_SOURCES}',
        '     ${COMMON_SOURCE_DIR}/m7_cn_lifecycle.c\n     ${USER_SOURCES}'))
    # All transformations must succeed before any file is replaced.
    for relative, text in changed.items():
        (tree / relative).write_text(text, encoding='utf-8', newline='\n')
    for name in ('m7_cn_lifecycle.c', 'm7_cn_lifecycle.h'):
        target = tree / ('stack/src/common' if name.endswith('.c') else 'stack/include/common') / name
        shutil.copyfile(OVERLAY / name, target)
    shutil.copyfile(STAGE / 'source/powerlink/linux-cn/transport/m7_cn_edrv.h',
                    tree / 'stack/include/common/m7_cn_edrv.h')
    return {relative: hashlib.sha256((tree / relative).read_bytes()).hexdigest() for relative in changed}
