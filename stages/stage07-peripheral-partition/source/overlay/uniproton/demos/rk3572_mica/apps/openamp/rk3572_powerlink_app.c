/* Dormant UP2 owner. One pending OR running command, no heap mailbox.
 * P3b exposes SOFTWARE environment only. No prepare/process/NMT/TX calls.
 * IRQ locks protect copies/claims, never wrap a stack API or RPMsg send.
 * This is pinned non-SMP UP2 code, not a cross-CPU queue or timing promise. */
#include "prt_config.h"
#include "prt_task.h"
#include "prt_hwi.h"
#include "cpu_config.h"
#include "test.h"
#include "rk3572_powerlink_app.h"
#include "m7_plk_platform.h"
#include <stdio.h>
#include <string.h>
#if MCS_CLIENT_CPU_ID != 5
#error "POWERLINK owner task belongs to UP2 only"
#endif
enum { ENV_INIT = 1U, ENV_EXIT = 2U };
#ifdef M7_POWERLINK_TIMER_PROBE
enum { TIMER_PROBE = 3U };
#endif
#ifdef M7_POWERLINK_ETH_PROBE
enum { ETH_PROBE = 4U };
#endif
#define APP_ERROR 0xffffffffU
static M7PowerlinkSnapshot snapshot;
static U8 ownerStack[0x8000] __attribute__((aligned(16)));
static TskHandle ownerTask;
static uint32_t attempted, initError;
extern int send_message(unsigned char* message, int length);

int Rk3572PowerlinkSnapshot(M7PowerlinkSnapshot* out)
{
    uintptr_t lock;
    if (!out) return 0;
    lock = PRT_HwiLock(); *out = snapshot; PRT_HwiRestore(lock);
    return 1;
}
static void Worker(uintptr_t a, uintptr_t b, uintptr_t c, uintptr_t d)
{
    (void)a; (void)b; (void)c; (void)d;
    for (;;) {
        uint32_t command = 0, result = 0, task = 0, valid;
        M7MnStatus state;
        uintptr_t lock;
        valid = m7_plk_task_id(&task) && task == ownerTask &&
            !m7_plk_in_interrupt() && m7_plk_irq_enabled();
        lock = PRT_HwiLock();
        if (!valid) { snapshot.ready = 0; snapshot.runtimeError = APP_ERROR; }
        if (valid && snapshot.ready && snapshot.pending) {
            command = snapshot.command; snapshot.pending = 0; snapshot.running = 1;
        }
        PRT_HwiRestore(lock);
        if (!valid) {
            PRT_Printf("[plk] invalid owner context; retained until reboot\n");
            return; /* Do not call a blocking RTOS API in an invalid context. */
        }
        if (command) {
#ifdef M7_POWERLINK_ETH_PROBE
            if (command == ETH_PROBE) {
                M7EthProbeResult eth;
                PRT_Printf("[plk-eth] BEGIN forced100-half; no DMA/MN/frame startup\n");
                result = m7_eth_probe(&eth);
                lock = PRT_HwiLock();
                snapshot.eth = eth; snapshot.result = result;
                snapshot.running = 0; snapshot.completed = snapshot.submitted;
                if (!eth.clean) { snapshot.ready = 0; snapshot.runtimeError = APP_ERROR; }
                PRT_HwiRestore(lock);
                PRT_Printf("[plk-eth] END rc=%u clean=%u phy=0x%x/0x%x bmcr=0x%x bmsr=0x%x mac=0x%x stop=0x%x/0x%x/0x%x lease=%u/%u\n",
                    result, eth.clean, eth.configured.phyHigh, eth.configured.phyLow,
                    eth.configured.bmcr, eth.configured.bmsr, eth.configured.mac,
                    eth.stopped.mac, eth.stopped.tx, eth.stopped.rx, eth.leaseBefore, eth.leaseAfter);
            } else {
#endif
#ifdef M7_POWERLINK_TIMER_PROBE
            if (command == TIMER_PROBE) {
                M7TimerProbeResult timer;
                PRT_Printf("[plk-timer] BEGIN CNTP access/PPI30; no Ethernet/MN startup\n");
                result = m7_timer_probe(&timer);
                lock = PRT_HwiLock();
                snapshot.timer = timer; snapshot.result = result;
                snapshot.running = 0; snapshot.completed = snapshot.submitted;
                if (!timer.clean) { snapshot.ready = 0; snapshot.runtimeError = APP_ERROR; }
                PRT_HwiRestore(lock);
                PRT_Printf("[plk-timer] END rc=%u clean=%u samples=%u irqs=%llu callbacks=%llu hz=%u irqLate=%llu taskLate=%llu ticks=%llu\n",
                    result, timer.clean, timer.samples, (unsigned long long)timer.after.interrupts,
                    (unsigned long long)timer.callbacks, timer.after.frequency,
                    (unsigned long long)timer.after.maxIrqLate, (unsigned long long)timer.maxTaskLate,
                    (unsigned long long)(timer.after.ticks - timer.before.ticks));
            } else {
#endif
            result = command == ENV_INIT ? m7_mn_initialize() : m7_mn_exit();
            /* Only the owner reads the real stack; consumers copy this cache. */
            if (m7_mn_status(&state)) {
                lock = PRT_HwiLock(); state = snapshot.mn; PRT_HwiRestore(lock);
                state.state = M7_MN_FAULT;
                state.lastError = result ? result : APP_ERROR;
            }
            lock = PRT_HwiLock();
            snapshot.mn = state; snapshot.result = result;
            snapshot.running = 0; snapshot.completed = snapshot.submitted;
            if (state.state == M7_MN_FAULT) snapshot.ready = 0;
            PRT_HwiRestore(lock);
            PRT_Printf("[plk] owner=%u command=%u rc=0x%x state=%u (software-only)\n",
                task, command, result, state.state);
#ifdef M7_POWERLINK_TIMER_PROBE
            }
#endif
#ifdef M7_POWERLINK_ETH_PROBE
            }
#endif
        }
        result = PRT_TaskDelay(2U);
        if (result) {
            lock = PRT_HwiLock(); snapshot.ready = 0; snapshot.runtimeError = result;
            PRT_HwiRestore(lock);
            /* Keep all live resources and task stack; no cleanup/retry/spin. */
            PRT_Printf("[plk] owner delay failed rc=%u; retained until reboot\n", result);
            return;
        }
    }
}
uint32_t Rk3572PowerlinkInit(void)
{
    struct TskInitParam param = {0};
    uint32_t ret;
    uintptr_t lock;
    if (attempted) return initError;
    attempted = 1;
    param.stackAddr = (uintptr_t)ownerStack; param.stackSize = sizeof(ownerStack);
    param.taskEntry = Worker; param.taskPrio = 24U; param.name = "PLKowner";
    ret = PRT_TaskCreate(&ownerTask, &param);
    if (!ret) {
        ret = PRT_TaskResume(ownerTask);
        if (ret) {
            uint32_t deleted = PRT_TaskDelete(ownerTask);
            if (deleted) PRT_Printf("[plk] dormant task delete failed rc=%u\n", deleted);
        }
    }
    lock = PRT_HwiLock();
    initError = ret; snapshot.runtimeError = ret;
    if (!ret) { snapshot.owner = ownerTask; snapshot.ready = 1; }
    PRT_HwiRestore(lock);
    PRT_Printf("[plk] dormant owner init rc=%u; no PHY/timer/MN startup\n", ret);
    return ret;
}
static int matches(const char* data, size_t length, const char* text)
{ return length == strlen(text) && !memcmp(data, text, length); }
int Rk3572PowerlinkInput(const char* data, size_t length)
{
    const char* error = NULL;
    uint32_t command = 0, accepted = 0;
#ifdef M7_POWERLINK_TIMER_PROBE
    int timerStatus = 0;
#endif
#ifdef M7_POWERLINK_ETH_PROBE
    int ethStatus = 0;
#endif
    M7PowerlinkSnapshot out;
    char reply[384];
    uintptr_t lock;
    int bytes;
    if (!data || length < 4 || memcmp(data, "PLK ", 4)) return 0;
    if (length > 48) error = "invalid-command";
    else {
        if (length && data[length-1] == '\n') {
            --length; if (length && data[length-1] == '\r') --length;
        }
        if (matches(data, length, "PLK env-init")) command = ENV_INIT;
        else if (matches(data, length, "PLK env-exit")) command = ENV_EXIT;
#ifdef M7_POWERLINK_TIMER_PROBE
        else if (matches(data, length, "PLK timer-probe")) command = TIMER_PROBE;
        else if (matches(data, length, "PLK timer-status")) timerStatus = 1;
#endif
#ifdef M7_POWERLINK_ETH_PROBE
        else if (matches(data, length, "PLK eth-probe")) command = ETH_PROBE;
        else if (matches(data, length, "PLK eth-status")) ethStatus = 1;
#endif
        else if (!matches(data, length, "PLK status")) error = "invalid-command";
    }
    lock = PRT_HwiLock();
    if (!error && command) {
        if (!snapshot.ready) error = "not-ready";
        else if (snapshot.pending || snapshot.running) error = "busy";
#ifdef M7_POWERLINK_TIMER_PROBE
        else if (command == TIMER_PROBE && snapshot.mn.state != M7_MN_COLD) error = "wrong-state";
#endif
#ifdef M7_POWERLINK_ETH_PROBE
        else if (command == ETH_PROBE && snapshot.mn.state != M7_MN_COLD) error = "wrong-state";
#endif
        else if ((command == ENV_INIT && snapshot.mn.state != M7_MN_COLD) ||
                 (command == ENV_EXIT && snapshot.mn.state != M7_MN_IDLE)) error = "wrong-state";
        else if (snapshot.submitted == UINT32_MAX) error = "sequence-exhausted";
        else {
            snapshot.command = command; ++snapshot.submitted;
            snapshot.pending = 1; accepted = snapshot.submitted;
        }
    }
    out = snapshot; PRT_HwiRestore(lock);
    if (error) bytes = snprintf(reply, sizeof(reply), "PLK UP2 ERROR %s\n", error);
    else if (accepted) bytes = snprintf(reply, sizeof(reply), "PLK UP2 ACCEPTED seq=%u\n", accepted);
#ifdef M7_POWERLINK_TIMER_PROBE
    else if (timerStatus) bytes = snprintf(reply, sizeof(reply),
        "PLK UP2 TIMER rc=%u clean=%u samples=%u hz=%u irqs=%llu callbacks=%llu irqLate=%llu taskLate=%llu ticks=%llu el=%u affinity=0x%llx ppi30=0x%x/0x%x/0x%x prio=%u/%u cntv=%u/%u\n",
        out.timer.result, out.timer.clean, out.timer.samples, out.timer.after.frequency,
        (unsigned long long)out.timer.after.interrupts, (unsigned long long)out.timer.callbacks,
        (unsigned long long)out.timer.after.maxIrqLate, (unsigned long long)out.timer.maxTaskLate,
        (unsigned long long)(out.timer.after.ticks - out.timer.before.ticks), out.timer.after.level,
        (unsigned long long)out.timer.after.affinity, out.timer.after.enabled & (1U << 30),
        out.timer.after.pending & (1U << 30), out.timer.after.active & (1U << 30),
        out.timer.before.priority30, out.timer.after.priority30, out.timer.before.cntv & 3U, out.timer.after.cntv & 3U);
#endif
#ifdef M7_POWERLINK_ETH_PROBE
    else if (ethStatus) bytes = snprintf(reply, sizeof(reply),
        "PLK UP2 ETH rc=%u clean=%u phy=0x%x/0x%x bmcr=0x%x bmsr=0x%x mac=0x%x tx=0x%x rx=0x%x dma=0x%x irq=0x%x/0x%x stop=0x%x/0x%x/0x%x/0x%x/0x%x/0x%x lease=%u/%u\n",
        out.eth.result, out.eth.clean, out.eth.configured.phyHigh, out.eth.configured.phyLow,
        out.eth.configured.bmcr, out.eth.configured.bmsr, out.eth.configured.mac,
        out.eth.configured.tx, out.eth.configured.rx, out.eth.configured.dma,
        out.eth.configured.macIrq, out.eth.configured.dmaIrq,
        out.eth.stopped.mac, out.eth.stopped.tx, out.eth.stopped.rx, out.eth.stopped.dma,
        out.eth.stopped.macIrq, out.eth.stopped.dmaIrq, out.eth.leaseBefore, out.eth.leaseAfter);
#endif
    else bytes = snprintf(reply, sizeof(reply),
        "PLK UP2 ready=%u owner=%u pending=%u running=%u seq=%u done=%u cmd=%u rc=0x%x runtime=0x%x state=%u nmt=0x%x processes=%llu events=%llu mode=software-only\n",
        out.ready, out.owner, out.pending, out.running, out.submitted, out.completed,
        out.command, out.result, out.runtimeError, out.mn.state, out.mn.nmtState,
        (unsigned long long)out.mn.processes, (unsigned long long)out.mn.events);
    if (bytes > 0 && bytes < (int)sizeof(reply)) {
        PRT_Printf("[plk] %s", reply); (void)send_message((unsigned char*)reply, bytes);
    }
    return 1;
}
