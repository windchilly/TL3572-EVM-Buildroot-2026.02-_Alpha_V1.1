/* Execute the PRODUCTION one-shot guard, not a host-implemented watchdog. */
#define M7_CYCLE_TEST_MAIN P3iRegressionMain
#define __wrap_oplk_execNmtCommand P3iWrapNmtCommand
#include "test_powerlink_cycle.c"
#undef __wrap_oplk_execNmtCommand
#include "m7_cycle_probe.h"
static const char* scenario;
static int injected;
uint32_t m7_eth2_hw_lease(void) { return (uint32_t)ethLease; }
tOplkError __wrap_oplk_execNmtCommand(tNmtEvent command)
{
    if ((!strcmp(scenario,"reset_command") && command==kNmtEventSwReset) ||
        (!strcmp(scenario,"off_command") && command==kNmtEventSwitchOff)) return kErrorNoResource;
    return P3iWrapNmtCommand(command);
}
int __real_m7_eth2_hw_acquire(void);
int __wrap_m7_eth2_hw_acquire(void)
{
    if (!strcmp(scenario,"total_budget")) { ticks+=24000000ULL*8;now=ticks/24000U; }
    return __real_m7_eth2_hw_acquire();
}
tOplkError __real_edrvcyclic_stopCycle(BOOL keep);
tOplkError __wrap_edrvcyclic_stopCycle(BOOL keep)
{
    if (!strcmp(scenario,"stop_cycle_failure") && nmtu_getNmtState()==kNmtMsOperational) return kErrorNoResource;
    return __real_edrvcyclic_stopCycle(keep);
}
uint32_t __real_m7_mn_process(void);
uint32_t __wrap_m7_mn_process(void)
{
    int operational=nmtu_getNmtState()==kNmtMsOperational;
    unsigned delta=50;
    if (operational && !injected) {
        injected=1;
        if (!strcmp(scenario,"no_completion")) stalledDma=1;
        if (!strcmp(scenario,"tx_error")) txError=1;
        if (!strcmp(scenario,"dma_fault")) dmaFault=1;
        if (!strcmp(scenario,"late")) delta=6000;
        if (!strcmp(scenario,"wrong_context")) { task=2; return kErrorOk; }
    }
    ticks+=(uint64_t)delta*24U; now=ticks/24000U; complete_dma();
    if (armed && (int64_t)(ticks-deadline)>=0) { ++irqs; isr=1; m7_hrestimer_interrupt(); isr=0; }
    if (!strcmp(scenario,"nmt_timeout") || (operational && !strcmp(scenario,"no_progress"))) return kErrorOk;
    return __real_m7_mn_process();
}
uint32_t __wrap_m7_eth2_hw_read(uint32_t offset)
{
    switch (offset) {
        case 0:return ethLease?0xc003U:0;
        case 0x1104:case 0x1108:return ethLease?1U:0;
        case 0x1000:case 0xb4:case 0x1134:return 0;
        case 0x1160:return dmaFault?1U<<12:0;
        default:assert(0);return 0;
    }
}
int m7_timer_diag_snapshot(M7TimerHardware* out)
{
    *out=(M7TimerHardware){0}; out->counter=ticks; out->ticks=now;
    out->level=4; out->frequency=24000000U; out->cntp=2; out->cntv=1;
    out->enabled=1U<<27; out->priority30=160; out->priority27=32;
    if (timerReleases && !strcmp(scenario,"readback")) out->cntv=0;
    return 1;
}
int main(int argc,char** argv)
{
    M7CycleProbeResult out,retry;
    unsigned savedStops,savedReleases,savedFrees;
    uint32_t result;
    assert(argc==2); scenario=argv[1];
    if (!strcmp(scenario,"context")) {
        isr=1;assert(m7_cycle_probe(&out)==M7_CYCLE_CONTEXT);isr=0;
        masked=1;assert(m7_cycle_probe(&out)==M7_CYCLE_CONTEXT);masked=0;
        assert(!allocations && !ethAcquires && !timerAcquires);
    }
    if (!strcmp(scenario,"heap_full")) { heapLimit=1048544; heapUsed=heapPeak=128U*1024U; }
    if (!strcmp(scenario,"heap_small")) { heapLimit=524256; heapUsed=heapPeak=128U*1024U; }
    if (!strcmp(scenario,"stop_failure")) stopFail=1;
    if (!strcmp(scenario,"timer_release_failure")) timerStopFail=1;
    result=m7_cycle_probe(&out);
    printf("P3j PRODUCTION guard %s result=0x%x stack=0x%x clean=%u stage=%u reset/off=%u/%u reached=0x%x loops=%u run/drain=%u/%u tx=%u pending=%u max=%u stopCalls=%u trips=%u context=%u SoC_mock=%u time_us=%llu heap_model=%zu live=%u\n",
        scenario,result,out.lifecycle.stackError,out.lifecycle.clean,out.lifecycle.stage,out.resetSubmitted,out.offSubmitted,
        out.reached,out.lifecycle.loops,out.runLoops,out.drainLoops,out.lifecycle.tx,out.pending,out.maxPending,
        out.stopCycleCalls,out.watchdogTrips,out.contextValid,frames[1],(unsigned long long)(ticks/24),heapPeak,live);
    fflush(stdout);
    if (result) fprintf(stderr,"mock DMA completed=%u doorbells=%u own0=0x%x own1=0x%x stalled=%d ETH=%d timer=%d\n",completed,doorbells,
        m7_edrv_test_dma.tx[0].d[3],m7_edrv_test_dma.tx[1].d[3],stalledDma,ethLease,timerLease);
    if (!strcmp(scenario,"normal") || !strcmp(scenario,"heap_full") || !strcmp(scenario,"context")) {
        assert(!result && out.lifecycle.clean && out.lifecycle.stage==9 && out.reached==kNmtMsOperational);
        assert(out.resetSubmitted==1 && out.offSubmitted==1 && out.stopCycleCalls==1);
        assert(!out.pending && out.runLoops && out.drainLoops && !out.watchdogTrips && out.contextValid);
        assert(!live && !sems && !ethLease && !timerLease && !armed && allocations==frees);
        assert(frames[1]>=90 && completed==doorbells && !budgetFailures);
        if (!strcmp(scenario,"heap_full")) assert(heapUsed==128U*1024U && heapLimit-heapPeak>=256U*1024U);
    } else {
        assert(result && !out.lifecycle.clean && out.watchdogTrips==1);
        if (!strcmp(scenario,"no_completion")) assert(result==M7_CYCLE_PENDING || result==M7_CYCLE_IDLE);
        if (!strcmp(scenario,"no_progress")) assert(result==M7_CYCLE_IDLE);
        if (!strcmp(scenario,"reset_command") || !strcmp(scenario,"off_command")) assert(result==M7_CYCLE_COMMAND && out.lifecycle.stackError==kErrorNoResource);
        if (!strcmp(scenario,"total_budget")) assert(result==M7_CYCLE_BUDGET && !out.resetSubmitted);
        if (!strcmp(scenario,"readback")) assert(result==M7_CYCLE_CLEANUP && ethStops==1 && timerReleases==1);
        if (!strcmp(scenario,"stop_cycle_failure")) assert(result==M7_CYCLE_STOP && out.stopCycleCalls==1 && !out.offSubmitted);
        if (!strcmp(scenario,"heap_small")) assert(out.lifecycle.stackError==kErrorPdoInitError && out.lifecycle.final.lastError==kErrorPdoInitError);
        if (!strcmp(scenario,"wrong_context")) { assert(!out.contextValid && !m7_plk_faulted()); task=1; }
        else assert(m7_plk_faulted());
        if (!strcmp(scenario,"no_completion") || !strcmp(scenario,"no_progress") || !strcmp(scenario,"late") || !strcmp(scenario,"dma_fault") ||
            !strcmp(scenario,"tx_error") || !strcmp(scenario,"wrong_context"))
            assert(!out.offSubmitted && !out.stopCycleCalls && ethLease && timerLease);
        savedStops=ethStops; savedReleases=timerReleases; savedFrees=frees;
        assert(m7_cycle_probe(&retry)==M7_CYCLE_CONTEXT);
        assert(ethStops==savedStops && timerReleases==savedReleases && frees==savedFrees);
    }
    /* Even successful execution is consumed, not a repeatable run API. */
    if (!result) { savedStops=ethStops; assert(m7_cycle_probe(&retry)==M7_CYCLE_CONTEXT && ethStops==savedStops); }
    printf("P3j native production diagnostic %s PASS; mock hardware only, ABI=%zu; NO BOARD\n",scenario,sizeof(out));
    return 0;
}
