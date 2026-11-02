/* P3i SOFTWARE ONLY: real full MN/NMT/OD/cyclic EDRV/target/timers.
 * Mock only RTOS primitives, 24MHz time, DMA completion and controller IO.
 * No board/PHY/CN, wire/FCS/latency proof, or application run command here.
 */
#define main PassiveRegressionMain
#define m7_plk_timer_now PassiveTimerNow
#define m7_plk_timer_arm PassiveTimerArm
#define m7_plk_timer_mask PassiveTimerMask
#define m7_eth2_hw_read PassiveRead
#define m7_eth2_hw_write PassiveWrite
#include "test_powerlink_passive_mn.c"
#undef main
#undef m7_plk_timer_now
#undef m7_plk_timer_arm
#undef m7_plk_timer_mask
#undef m7_eth2_hw_read
#undef m7_eth2_hw_write
#include "m7_edrv.h"
#include <kernel/edrvcyclic.h>
#include <execinfo.h>
static uint64_t ticks, deadline;
static int armed, dmaFault, txError, stalledDma;
static unsigned arms, irqs, doorbells, completed, frames[8];
static unsigned resetCommands, offCommands;
uint32_t m7_eth2_hw_read(uint32_t offset)
{
    assert(offset == 0x1160);
    return dmaFault ? 1U << 12 : 0;
}
tOplkError __real_edrv_freeTxBuffer(tEdrvTxBuffer* buffer);
tOplkError __wrap_edrv_freeTxBuffer(tEdrvTxBuffer* buffer)
{
    tOplkError rc = __real_edrv_freeTxBuffer(buffer);
    if (rc) fprintf(stderr, "P3i freeTxBuffer failed rc=0x%x buffer=%p slot=%llu\n", rc, (void*)buffer,
        (unsigned long long)buffer->txBufferNumber.value);
    return rc;
}
void __real_m7_plk_fault(void);
void __wrap_m7_plk_fault(void)
{
    void* trace[24];
    int count = backtrace(trace, 24);
    fprintf(stderr, "P3i native fault at %lluus\n", (unsigned long long)(ticks/24));
    backtrace_symbols_fd(trace, count, 2);
    __real_m7_plk_fault();
}

uint64_t m7_plk_timer_now(void) { return ticks; }
void m7_plk_timer_arm(uint64_t value)
{
    assert(timerLease && m7_plk_owner() && masked);
    deadline = value; armed = 1; ++arms;
}
void m7_plk_timer_mask(void) { armed = 0; }
void m7_eth2_hw_write(uint32_t offset, uint32_t value)
{
    assert(ethLease && m7_plk_ready() && !isr);
    assert(offset == 0x1160 || offset == 0x1120);
    if (offset == 0x1160) assert(value == (1U << 2));
    else ++doorbells;
    ++writes;
}
tOplkError __real_oplk_execNmtCommand(tNmtEvent command);
tOplkError __wrap_oplk_execNmtCommand(tNmtEvent command)
{
    assert(command == kNmtEventSwReset || command == kNmtEventSwitchOff);
    if (command == kNmtEventSwReset) ++resetCommands; else ++offCommands;
    return __real_oplk_execNmtCommand(command);
}
static void complete_dma(void)
{
    unsigned i, j;
    if (stalledDma) return;
    for (i = 0; i < M7_ETH2_RING; ++i) {
        struct M7Eth2Desc* desc = &m7_edrv_test_dma.tx[i];
        if (!(desc->d[3] & M7_ETH2_OWN)) continue;
        for (j = 0; j < M7_ETH2_TX_BUFFERS; ++j)
            if (desc->d[0] == (uint32_t)(uintptr_t)m7_edrv_test_dma.txbuf[j]) break;
        assert(j < M7_ETH2_TX_BUFFERS && desc->d[2] >= 17);
        const uint8_t* packet = m7_edrv_test_dma.txbuf[j];
        assert(packet[12] == 0x88 && packet[13] == 0xab && packet[14] < 8);
        if (txError) { desc->d[3] = (desc->d[3] & ~M7_ETH2_OWN) | M7_ETH2_ERROR; continue; }
        ++frames[packet[14]]; ++completed;
        desc->d[3] &= ~M7_ETH2_OWN; /* Explicit MOCK, not physical completion. */
    }
}
static uint32_t step(unsigned microseconds)
{
    ticks += (uint64_t)microseconds * 24U; now = ticks / 24000U;
    complete_dma();
    if (armed && (int64_t)(ticks - deadline) >= 0) {
        ++irqs; isr = 1; m7_hrestimer_interrupt(); isr = 0;
    }
    return m7_mn_process();
}
#ifndef M7_CYCLE_TEST_MAIN
#define M7_CYCLE_TEST_MAIN main
#endif
int M7_CYCLE_TEST_MAIN(int argc, char** argv)
{
    unsigned iteration, i, rounds;
    const char* scenario;
    assert(argc == 2); scenario = argv[1];
    rounds = (!strcmp(scenario,"normal") || !strcmp(scenario,"heap_full")) ? 10U : 1U;
    if (!strcmp(scenario,"heap_full")) {
        heapLimit = 1048544U; heapUsed = heapPeak = 128U*1024U;
    }
    for (iteration = 0; iteration < rounds; ++iteration) {
        unsigned startSoc = frames[1], startCompleted = completed;
        uint32_t last = UINT32_MAX;
        assert(m7_mn_initialize() == kErrorOk); prepare_ok();
        assert(oplk_execNmtCommand(kNmtEventSwReset) == kErrorOk);
        for (i = 0; i < 60000; ++i) {
            uint32_t rc = step(50);
            M7MnStatus status = snapshot();
            if (!iteration && (status.nmtState != last || rc)) {
                printf("REAL NMT state=0x%x rc=0x%x first=0x%x t=%lluus SoC=%u tx=%u\n",
                    status.nmtState, rc, status.lastError, (unsigned long long)(ticks/24), frames[1], completed);
                fflush(stdout); last = status.nmtState;
            }
            assert(rc == kErrorOk);
            if (status.nmtState == kNmtMsOperational && frames[1] - startSoc >= 128) break;
        }
        assert(i < 60000 && snapshot().nmtState == kNmtMsOperational);
        if (!strcmp(scenario,"wrong_owner")) {
            unsigned savedWrites = writes;
            task = 2; assert(m7_mn_process() == kErrorInvalidOperation && m7_mn_stop() == kErrorInvalidOperation);
            assert(writes == savedWrites && ethLease && timerLease); task = 1;
        }
        if (!strcmp(scenario,"dma_fault") || !strcmp(scenario,"tx_error") || !strcmp(scenario,"no_completion")) {
            uint32_t rc = kErrorOk;
            unsigned progress = completed;
            if (!strcmp(scenario,"dma_fault")) dmaFault = 1;
            else if (!strcmp(scenario,"tx_error")) txError = 1;
            else stalledDma = 1;
            for (i = 0; i < 500 && !rc; ++i) rc = step(50);
            if (!strcmp(scenario,"no_completion")) {
                /* Expose a real integration GAP, do not pretend the old stack
                 * has a production progress watchdog: it can keep returning
                 * OK with stalled TX. This HOST policy prototype refuses to
                 * free/release after its bounded 25ms observation window. */
                assert(!rc && !m7_plk_faulted() && completed == progress);
                puts("P3i GAP: stalled TX did not fault automatically; HOST 25ms progress guard marks terminal, not an RTOS watchdog implementation");
                m7_plk_fault(); rc = kErrorReject;
            }
            assert(rc && m7_plk_faulted() && ethLease && timerLease);
            unsigned savedStops = ethStops, savedReleases = timerReleases, savedFrees = frees;
            assert(m7_mn_stop() == kErrorInvalidOperation && m7_mn_exit() == kErrorInvalidOperation);
            assert(savedStops == ethStops && savedReleases == timerReleases && savedFrees == frees);
            printf("P3i cycle fault %s retained; rc=0x%x first=0x%x completed_mock=%u submitted=%u live=%u\n",
                scenario,rc,snapshot().lastError,completed,doorbells,live); return 0;
        }
        /* SOFTWARE ordering experiment: stop future cyclic submissions, then
         * retire already submitted DMA through the real EDRV poll BEFORE
         * NMT is allowed to delete frame owners. Never erase EDRV busy flags
         * to fake a drain. The physical completion boundary is still mocked. */
        if (strcmp(scenario,"direct_off")) {
            assert(edrvcyclic_stopCycle(FALSE) == kErrorOk);
            for (i = 0; i < 8; ++i) assert(step(50) == kErrorOk);
            assert(!armed && completed == doorbells);
        }
        assert(oplk_execNmtCommand(kNmtEventSwitchOff) == kErrorOk);
        for (i = 0; i < 32 && nmtu_getNmtState() != kNmtGsOff; ++i) {
            uint32_t rc = step(50);
            if (rc) fprintf(stderr,"SwitchOff process rc=0x%x first=0x%x event=%u state=0x%x completed=%u submitted=%u\n",
                rc,snapshot().lastError,snapshot().lastEvent,snapshot().nmtState,completed,doorbells);
            if (rc && !strcmp(scenario,"direct_off")) {
                assert(m7_plk_faulted() && ethLease && timerLease && !ethStops && !timerReleases);
                assert(m7_mn_stop() == kErrorInvalidOperation && m7_mn_exit() == kErrorInvalidOperation);
                puts("P3i direct SwitchOff rejected busy buffer; resources retained, no unsafe free/retry"); return 0;
            }
            assert(rc == kErrorOk);
        }
        assert(i < 32 && nmtu_getNmtState() == kNmtGsOff && !armed);
        assert(strcmp(scenario,"direct_off"));
        if (!strcmp(scenario,"stop_failure") || !strcmp(scenario,"timer_release_failure")) {
            unsigned savedFrees = frees;
            if (!strcmp(scenario,"stop_failure")) stopFail = 1; else timerStopFail = 1;
            assert(m7_mn_stop() != kErrorOk && m7_plk_faulted() && timerLease);
            assert(frees == savedFrees && live && m7_mn_exit() == kErrorInvalidOperation);
            if (stopFail) assert(ethLease && !timerReleases); else assert(!ethLease);
            printf("P3i %s retained after real cyclic run, no false cleanup\n",scenario); return 0;
        }
        assert(m7_mn_stop() == kErrorOk && m7_mn_exit() == kErrorOk);
        assert(!live && !sems && !m7_plk_owner() && !ethLease && !timerLease && !armed && !budgetFailures);
        assert(heapUsed == (!strcmp(scenario,"heap_full") ? 128U*1024U : 0U));
        assert(completed > startCompleted && frames[1] - startSoc >= 128);
    }
    assert(resetCommands == rounds && offCommands == rounds && allocations == frees);
    assert(!strcmp(scenario,"normal") || !strcmp(scenario,"heap_full") || !strcmp(scenario,"wrong_owner"));
    if (!strcmp(scenario,"heap_full")) assert(heapLimit - heapPeak >= 256U*1024U);
    printf("P3i REAL MN cycle software PASS: scenario=%s rounds=%u reset=%u off=%u SoC=%u SoA=%u ASnd=%u tx_completed_mock=%u doorbells=%u timer_arms=%u IRQ_mock=%u heap_peak_model=%zu live=%u; NO BOARD/real CN/realtime guarantee\n",
        scenario, rounds, resetCommands, offCommands, frames[1], frames[5], frames[6], completed, doorbells, arms, irqs, heapPeak, live);
    return 0;
}
