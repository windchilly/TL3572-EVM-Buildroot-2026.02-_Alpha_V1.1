/* P3j one owner, full original OD, no CN plan. No automatic recovery/retry. */
#include <oplk/oplk.h>
#include <user/nmtu.h>
#include <kernel/edrvcyclic.h>
#include "m7_cycle_probe.h"
#include "m7_edrv.h"
#include "m7_eth2_hw.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
static int attempted;
static int context(uint32_t owner)
{
    uint32_t task;
    return !m7_plk_in_interrupt() && m7_plk_irq_enabled() && m7_plk_task_id(&task) && task == owner;
}
static void hardware(M7EthHardware* out)
{
    out->mac=m7_eth2_hw_read(0); out->tx=m7_eth2_hw_read(0x1104); out->rx=m7_eth2_hw_read(0x1108);
    out->dma=m7_eth2_hw_read(0x1000); out->macIrq=m7_eth2_hw_read(0xb4); out->dmaIrq=m7_eth2_hw_read(0x1134);
}
static int rank(uint32_t nmt)
{
    switch (nmt) {
        case kNmtGsOff:return 0; case kNmtGsInitialising:return 1; case kNmtGsResetApplication:return 2;
        case kNmtGsResetCommunication:return 3; case kNmtGsResetConfiguration:return 4;
        case kNmtMsNotActive:return 5; case kNmtMsPreOperational1:return 6;
        case kNmtMsPreOperational2:return 7; case kNmtMsReadyToOperate:return 8; case kNmtMsOperational:return 9;
        default:return -1;
    }
}
static uint64_t us(uint32_t value) { return (uint64_t)value*24U; }
static int config(void)
{
    uint32_t value, i;
    size_t bytes=sizeof(value);
    if (oplk_readLocalObject(0x1006,0,&value,&bytes) || bytes!=4 || value!=1000U) return 0;
    for (i=1;i<=254;++i) {
        bytes=sizeof(value);
        if (oplk_readLocalObject(0x1f81,i,&value,&bytes) || bytes!=4 || value) return 0;
    }
    return 1;
}
/* Called before and after EVERY process pass. No ISR hardware access or
 * post-fault cleanup. Progress counters are real EDRV completion callbacks. */
static uint32_t clockBudget(M7CycleProbeResult* out)
{
    uint64_t now, gap;
    if (!context(out->owner)) { out->contextValid=0; return M7_CYCLE_CONTEXT; }
    out->contextValid=1;
    now=m7_plk_timer_now(); gap=now-out->endCounter; out->endCounter=now;
    if (gap>out->maxGapTicks) out->maxGapTicks=gap;
    if (now-out->startCounter>=us(M7_CYCLE_TOTAL_MS*1000U) || out->lifecycle.loops>=M7_CYCLE_MAX_LOOPS)
        return M7_CYCLE_BUDGET;
    return 0;
}
static uint32_t sample(M7CycleProbeResult* out, int progress)
{
    M7MnProbeResult* life=&out->lifecycle;
    M7PlkTimerStats timer={0};
    const tM7EdrvStats* stats=m7_edrv_stats();
    uint64_t now;
    uint32_t pending, previousPending=out->pending, result=clockBudget(out);
    if (result) return result;
    now=out->endCounter;
    if (m7_mn_status(&life->final) || life->final.owner!=out->owner || life->final.state!=M7_MN_PREPARED)
        return M7_CYCLE_STATE;
    pending=m7_edrv_tx_pending();
    if (pending>=M7_ETH2_RING) return M7_CYCLE_IO;
    out->pending=pending; if (pending>out->maxPending) out->maxPending=pending;
    if (stats->txCompleted<life->tx || stats->txCompleted>M7_CYCLE_TOTAL_TX-pending) return M7_CYCLE_IO;
    if (!pending || !previousPending || stats->txCompleted!=life->tx) out->pendingCounter=now;
    if (stats->txCompleted!=life->tx || !progress || rank(life->final.nmtState)<6) out->lastTxCounter=now;
    life->tx=stats->txCompleted; life->rx=stats->rxDelivered; life->dropped=stats->rxDropped;
    life->rxErrors=stats->rxErrors; life->txErrors=stats->txErrors; life->fatal=stats->dmaFatal;
    m7_hrestimer_stats(&timer); out->frequency=timer.frequency;
    out->maxLateTicks=timer.max_late_ticks; out->skippedPeriods=timer.skipped_periods;
    life->timerIrqs=timer.interrupts; life->timerCallbacks=timer.callbacks;
    if (life->rx || life->rxErrors || life->txErrors || life->fatal || stats->rxDeferredRejected) return M7_CYCLE_IO;
    if (!timer.leased || timer.frequency!=24000000U || timer.dispatching ||
        timer.skipped_periods || timer.max_late_ticks>us(M7_CYCLE_MAX_LATE_US)) return M7_CYCLE_TIMER;
    if (progress && pending && now-out->pendingCounter>=us(M7_CYCLE_PENDING_US)) return M7_CYCLE_PENDING;
    if (progress && rank(life->final.nmtState)>=6 && now-out->lastTxCounter>=us(M7_CYCLE_IDLE_US)) return M7_CYCLE_IDLE;
    return 0;
}
static uint32_t process(M7CycleProbeResult* out, int progress)
{
    uint32_t result=sample(out,progress);
    if (result) return result;
    out->lifecycle.stackError=m7_mn_process(); ++out->lifecycle.loops;
    if (out->lifecycle.stackError) return M7_CYCLE_PROCESS;
    return sample(out,progress);
}
uint32_t m7_cycle_probe(M7CycleProbeResult* out)
{
    M7MnProbeResult* life;
    uint32_t result=M7_CYCLE_CONTEXT, task, total;
    uint64_t phase, quiet;
    int previous=0;
    if (!out) return result;
    *out=(M7CycleProbeResult){0}; out->abi=M7_CYCLE_ABI; out->bytes=sizeof(*out); life=&out->lifecycle;
    if (!m7_plk_task_id(&task) || !context(task)) return life->result=result;
    out->owner=task; out->contextValid=1;
    life->leaseBefore=life->leaseAfter=m7_eth2_hw_lease(); life->timerBefore=life->timerAfter=m7_hrestimer_active();
    if (attempted || life->leaseBefore || life->timerBefore || m7_plk_owner() || m7_plk_faulted() ||
        !m7_timer_diag_snapshot(&life->timerInitial) || life->timerInitial.frequency!=24000000U)
        return life->result=result;
    attempted=1; out->startCounter=out->endCounter=life->timerInitial.counter;
    life->stage=1; life->stackError=m7_mn_initialize();
    if (life->stackError) { result=M7_CYCLE_PROCESS; goto unsafe; }
    if (m7_mn_status(&life->initialized)) { result=M7_CYCLE_STATE; goto unsafe; }
    life->stage=2; life->stackError=m7_mn_prepare();
    if (life->stackError) { result=M7_CYCLE_PROCESS; goto unsafe; }
    if (m7_mn_status(&life->prepared)) { result=M7_CYCLE_STATE; goto unsafe; }
    hardware(&life->active);
    if ((life->active.mac&0x0030e003U)!=0xc003U || !(life->active.tx&1U) || !(life->active.rx&1U) ||
        (life->active.dma&1U) || life->active.macIrq || life->active.dmaIrq || !config()) { result=M7_CYCLE_CONFIG; goto unsafe; }
    result=sample(out,0); if (result) goto unsafe;
    if (life->final.nmtState!=kNmtGsOff || out->pending || life->tx || m7_hrestimer_pending()) { result=M7_CYCLE_STATE; goto unsafe; }
    life->stage=3; life->stackError=oplk_execNmtCommand(kNmtEventSwReset);
    if (life->stackError) { result=M7_CYCLE_COMMAND; goto unsafe; }
    out->resetSubmitted=1; phase=m7_plk_timer_now(); out->lastTxCounter=phase;
    for (;;) {
        result=process(out,1); if (result) goto unsafe;
        if (rank(life->final.nmtState)<previous) { result=M7_CYCLE_STATE; goto unsafe; }
        previous=rank(life->final.nmtState);
        if (previous<0) { result=M7_CYCLE_STATE; goto unsafe; }
        if (out->endCounter-phase>=us(M7_CYCLE_NMT_MS*1000U)) { result=M7_CYCLE_BUDGET; goto unsafe; }
        if (previous==9) break;
    }
    out->reached=kNmtMsOperational; life->stage=4; out->runCounter=out->endCounter; out->txBeforeRun=life->tx;
    do {
        result=process(out,1); ++out->runLoops; if (result) goto unsafe;
        if (life->final.nmtState!=kNmtMsOperational) { result=M7_CYCLE_STATE; goto unsafe; }
    } while (out->endCounter-out->runCounter<us(M7_CYCLE_RUN_MS*1000U) && life->tx-out->txBeforeRun<M7_CYCLE_RUN_TX);
    if (life->tx==out->txBeforeRun || !life->timerIrqs || !life->timerCallbacks) { result=M7_CYCLE_IDLE; goto unsafe; }
    life->stage=5; out->pendingAtStop=out->pending; out->txAtStop=life->tx; out->stopCycleCalls=1;
    life->stackError=edrvcyclic_stopCycle(FALSE);
    if (life->stackError) { result=M7_CYCLE_STOP; goto unsafe; }
    if (m7_hrestimer_pending()) { result=M7_CYCLE_TIMER; goto unsafe; }
    phase=quiet=m7_plk_timer_now(); total=life->tx+out->pending; life->stage=6;
    do {
        result=process(out,0); ++out->drainLoops; if (result) goto unsafe;
        if (life->final.nmtState!=kNmtMsOperational || m7_hrestimer_pending() || life->tx+out->pending!=total) { result=M7_CYCLE_DRAIN; goto unsafe; }
        if (out->pending) quiet=out->endCounter;
        if (out->endCounter-phase>=us(M7_CYCLE_DRAIN_US)) { result=M7_CYCLE_DRAIN; goto unsafe; }
    } while (out->pending || out->endCounter-quiet<us(M7_CYCLE_QUIET_US));
    life->stage=7; life->stackError=oplk_execNmtCommand(kNmtEventSwitchOff);
    if (life->stackError) { result=M7_CYCLE_COMMAND; goto unsafe; }
    out->offSubmitted=1;
    do {
        result=process(out,0); ++out->offLoops; if (result) goto unsafe;
        if (out->pending || life->tx!=total || m7_hrestimer_pending() ||
            (life->final.nmtState!=kNmtMsOperational && life->final.nmtState!=kNmtGsOff)) { result=M7_CYCLE_STATE; goto unsafe; }
        if (out->offLoops>=32U && life->final.nmtState!=kNmtGsOff) { result=M7_CYCLE_BUDGET; goto unsafe; }
    } while (life->final.nmtState!=kNmtGsOff);
    life->stage=8; life->stackError=m7_mn_stop();
    if (life->stackError) { result=M7_CYCLE_STOP; goto unsafe; }
    result=clockBudget(out); if (result) goto unsafe;
    hardware(&life->stopped); life->leaseAfter=m7_eth2_hw_lease(); life->timerAfter=m7_hrestimer_active();
    if (life->leaseAfter || life->timerAfter || (life->stopped.mac&3U) || (life->stopped.tx&1U) || (life->stopped.rx&1U) ||
        (life->stopped.dma&1U) || life->stopped.macIrq || life->stopped.dmaIrq || !m7_timer_diag_snapshot(&life->timerFinal) ||
        (life->timerFinal.cntp&1U) || ((life->timerFinal.enabled|life->timerFinal.pending|life->timerFinal.active)&(1U<<30)) ||
        ((life->timerInitial.cntv^life->timerFinal.cntv)&3U) ||
        ((life->timerInitial.enabled^life->timerFinal.enabled)&(1U<<27)) ||
        life->timerInitial.priority27!=life->timerFinal.priority27 || life->timerInitial.priority30!=life->timerFinal.priority30 ||
        life->timerInitial.affinity!=life->timerFinal.affinity || life->timerInitial.typer!=life->timerFinal.typer ||
        life->timerInitial.cpuControl!=life->timerFinal.cpuControl ||
        ((life->timerInitial.group^life->timerFinal.group)&(1U<<30)) ||
        ((life->timerInitial.config^life->timerFinal.config)&(1U<<29)) || life->timerFinal.frequency!=24000000U ||
        life->timerInitial.level!=4 || life->timerFinal.level!=4 || life->timerFinal.counter<life->timerInitial.counter) {
        result=M7_CYCLE_CLEANUP; goto unsafe;
    }
    life->stage=9; life->stackError=m7_mn_exit();
    if (life->stackError) { result=M7_CYCLE_EXIT; goto unsafe; }
    result=clockBudget(out); if (result) goto unsafe;
    if (m7_mn_status(&life->final) || life->final.state!=M7_MN_COLD || m7_plk_owner() || m7_plk_faulted()) {
        result=M7_CYCLE_CLEANUP; goto unsafe;
    }
    life->clean=1; return life->result=0;
unsafe:
    life->result=result; /* First reason and stack error are never overwritten by a secondary process(). */
    ++out->watchdogTrips;
    life->leaseAfter=m7_eth2_hw_lease(); life->timerAfter=m7_hrestimer_active();
    if (context(out->owner)) {
        const tM7EdrvStats* stats=m7_edrv_stats();
        M7PlkTimerStats timer={0};
        /* Capture the first failing pass, not the preceding healthy sample. */
        life->tx=stats->txCompleted; life->rx=stats->rxDelivered; life->dropped=stats->rxDropped;
        life->rxErrors=stats->rxErrors; life->txErrors=stats->txErrors; life->fatal=stats->dmaFatal;
        (void)m7_mn_status(&life->final);
        if (!life->stackError && life->final.lastError) life->stackError=life->final.lastError;
        if (m7_plk_owner()) {
            m7_hrestimer_stats(&timer); out->maxLateTicks=timer.max_late_ticks; out->skippedPeriods=timer.skipped_periods;
            life->timerIrqs=timer.interrupts; life->timerCallbacks=timer.callbacks;
        }
        m7_plk_fault();
    }
    else out->contextValid=0; /* Do NOT mask another context's CNTP or call stack APIs. */
    return result;
}
