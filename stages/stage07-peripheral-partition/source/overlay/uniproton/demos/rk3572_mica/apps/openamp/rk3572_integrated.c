/* Cumulative firmware. Boot is passive: only explicit commands queue hardware tests. */
#include "prt_config.h"
#include "prt_hwi.h"
#include "prt_task.h"
#include "cpu_config.h"
#include "test.h"
#include "rk3572_integrated.h"
#include "rk3572_integrated_command.h"
#include <stdio.h>
#include <string.h>

struct M7Job { U32 pending, running, value, result, completed; };
static struct M7Job g_jobs[M7_MODULES];
static U8 g_stacks[M7_MODULES][0x4000] __attribute__((aligned(16)));
static TskHandle g_tasks[M7_MODULES];
static U32 g_ready;
extern int send_message(unsigned char *message, int len);

static void Worker(uintptr_t index, uintptr_t unused1, uintptr_t unused2, uintptr_t unused3)
{
    (void)unused1; (void)unused2; (void)unused3;
    for (;;) {
        U32 value = 0U, work, ret;
        uintptr_t lock = PRT_HwiLock();
        work = g_jobs[index].pending;
        if (work) {
            value = g_jobs[index].value; g_jobs[index].pending = 0U; g_jobs[index].running = 1U;
        }
        PRT_HwiRestore(lock);
        if (work) {
            PRT_Printf("[integrated] UP%u begin module=%u value=%u\n", MCS_CLIENT_CPU_ID - 3U, (U32)index, value);
            if (index == 0U) { ret = value == 1U ? Rk3572CanClassicTest() : Rk3572CanFdTest(value); }
            else if (index == 1U) { ret = Rk3572Rs232Test(value); }
            else { ret = Rk3572Rs485Test(value); }
            lock = PRT_HwiLock();
            g_jobs[index].result = ret; g_jobs[index].running = 0U; g_jobs[index].completed++;
            PRT_HwiRestore(lock);
            PRT_Printf("[integrated] UP%u end module=%u rc=%u\n", MCS_CLIENT_CPU_ID - 3U, (U32)index, ret);
        }
        (void)PRT_TaskDelay(2U);
    }
}

U32 Rk3572IntegratedInit(void)
{
    U32 i, created = 0U, ret;
    if (g_ready) { return 0U; }
    for (i = 0U; i < M7_MODULES; i++) {
        struct TskInitParam param = {0};
        param.stackAddr = (uintptr_t)g_stacks[i]; param.stackSize = sizeof(g_stacks[i]);
        param.taskEntry = Worker; param.taskPrio = 26U + i; param.name = "M7worker"; param.args[0] = i;
        ret = PRT_TaskCreate(&g_tasks[i], &param);
        if (ret) { goto fail; }
        created++;
    }
    for (i = 0U; i < M7_MODULES; i++) {
        ret = PRT_TaskResume(g_tasks[i]);
        if (ret) { goto fail; }
    }
    g_ready = 1U;
    PRT_Printf("[integrated] UP%u ready modules=can-classic,can-fd,rs232,rs485 mode=passive\n", MCS_CLIENT_CPU_ID - 3U);
    return 0U;
fail:
    /* No command can be accepted until ready, so partial workers never touch hardware. */
    for (i = 0U; i < created; i++) { (void)PRT_TaskDelete(g_tasks[i]); }
    PRT_Printf("[integrated] worker init failed rc=%u\n", ret);
    return ret;
}

int Rk3572IntegratedInput(const char *data, size_t length)
{
    struct M7Command command = {0};
    U32 i, pending = 0U, running = 0U, results[M7_MODULES], completed[M7_MODULES], accepted = 0U;
    char reply[160];
    const char *error = NULL;
    uintptr_t lock;
    int size;
    /* Ordinary M6 RPMsg echo stays compatible; commands occupy one bounded RPMsg record. */
    if (length < 3U || memcmp(data, "M7 ", 3U)) { return 0; }
    if (!M7ParseCommand(data, length, &command)) { error = "invalid-command"; }
    lock = PRT_HwiLock();
    for (i = 0U; i < M7_MODULES; i++) {
        pending |= g_jobs[i].pending << i; running |= g_jobs[i].running << i; results[i] = g_jobs[i].result;
        completed[i] = g_jobs[i].completed;
    }
    if (!error && !g_ready) { error = "not-ready"; }
    if (!error && (command.mask & (pending | running))) { error = "busy"; }
    if (!error && command.mask) {
        for (i = 0U; i < M7_MODULES; i++) {
            if (command.mask & (1U << i)) {
                g_jobs[i].value = command.value[i]; g_jobs[i].pending = 1U;
            }
        }
        accepted = command.mask;
    }
    PRT_HwiRestore(lock);
    if (error) { size = snprintf(reply, sizeof(reply), "M7 UP%u ERROR %s\n", MCS_CLIENT_CPU_ID - 3U, error); }
    else if (accepted) {
        size = snprintf(reply, sizeof(reply), "M7 UP%u ACCEPTED mask=0x%x\n", MCS_CLIENT_CPU_ID - 3U, accepted);
    } else {
        size = snprintf(reply, sizeof(reply), "M7 UP%u ready=%u pending=0x%x running=0x%x rc=%u/%u/%u done=%u/%u/%u\n",
                        MCS_CLIENT_CPU_ID - 3U, g_ready, pending, running, results[0], results[1], results[2],
                        completed[0], completed[1], completed[2]);
    }
    if (size > 0 && size < (int)sizeof(reply)) {
        PRT_Printf("[integrated] %s", reply);
        (void)send_message((unsigned char *)reply, size);
    }
    return 1;
}
