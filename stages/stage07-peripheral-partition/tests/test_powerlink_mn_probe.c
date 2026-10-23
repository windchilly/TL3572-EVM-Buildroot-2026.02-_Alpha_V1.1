/* Reuse REAL full-stack fixture, replacing only mocked hardware/time hooks. */
#define main PassiveRegressionMain
#define m7_plk_sleep PassiveNoSleep
#define m7_eth2_hw_read PassiveStatusRead
#include "test_powerlink_passive_mn.c"
#undef main
#undef m7_plk_sleep
#undef m7_eth2_hw_read
#include "m7_mn_probe.h"
static int sleepFail, dmaFault, wrongMode, wrongReadback, touchedTx, slow;
uint32_t m7_eth2_hw_lease(void) { return (uint32_t)ethLease; }
uint32_t m7_eth2_hw_read(uint32_t offset)
{
    switch (offset) {
        case 0: return ethLease ? (wrongMode ? 0xe003U : 0xc003U) : 0;
        case 0x1104: case 0x1108: return ethLease ? 1U : 0;
        case 0x1000: case 0xb4: case 0x1134: return 0;
        case 0x1160: return dmaFault && now ? 1U << 12 : 0;
        default: assert(0); return 0;
    }
}
int m7_plk_sleep(uint32_t ms)
{
#ifdef M7_NMT_PROBE_TEST
    assert((ms == 1U || ms == CONFIG_PDO_SETUP_WAIT_TIME) && m7_plk_ready());
#else
    assert(ms == 1U && m7_plk_ready());
#endif
    now += slow ? 1000 : ms;
    if (touchedTx) m7_edrv_test_dma.tx[0].d[0] = 0x7ca10000;
    return !sleepFail;
}
int m7_timer_diag_snapshot(M7TimerHardware* out)
{
    *out = (M7TimerHardware){0}; out->cntp = 2; out->cntv = 1;
    out->enabled = 1U << 27; out->priority30 = 160; out->priority27 = 32;
    if (wrongReadback && timerReleases) out->priority27 = 99;
    return 1;
}
#ifndef M7_MN_PROBE_TEST_MAIN
#define M7_MN_PROBE_TEST_MAIN main
#endif
int M7_MN_PROBE_TEST_MAIN(int argc, char** argv)
{
    M7MnProbeResult out; uint32_t expected = M7_MPROBE_OK; unsigned i, stops, releases;
    assert(argc == 2 && m7_mn_probe(NULL) == M7_MPROBE_CONTEXT);
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            assert(!m7_mn_probe(&out) && out.clean && out.stage == 5 && out.loops == 128);
            assert(out.initialized.state == M7_MN_IDLE && out.prepared.state == M7_MN_PREPARED);
            assert(out.final.state == M7_MN_COLD && out.final.nmtState == kNmtGsOff);
            assert(out.final.processes == (uint64_t)(i + 1) * 128 && !out.final.events);
            assert(!out.tx && !out.txDescriptors && !out.timerIrqs && !out.timerCallbacks);
            assert(!out.leaseAfter && !out.timerAfter && !live && !sems && !m7_plk_owner());
        }
        assert(ethStops == 100 && timerReleases == 100 && allocations == frees && !writes);
        printf("P3f 100 REAL full-stack lifecycles: 12800 processes, %u alloc/free, GsOff, no TX/timer arm\n", frees);
        return 0;
    }
    if (!strcmp(argv[1], "context")) {
        isr = 1; assert(m7_mn_probe(&out) == M7_MPROBE_CONTEXT); isr = 0;
        masked = 1; assert(m7_mn_probe(&out) == M7_MPROBE_CONTEXT); masked = 0;
        ethLease = 1; assert(m7_mn_probe(&out) == M7_MPROBE_CONTEXT); ethLease = 0;
        assert(target_init() == kErrorOk && m7_mn_probe(&out) == M7_MPROBE_CONTEXT);
        assert(!allocations && !timerAcquires && !ethAcquires); return 0;
    }
    if (!strcmp(argv[1], "phy")) phyFail = 1, expected = M7_MPROBE_PREPARE;
    else if (!strcmp(argv[1], "timer")) timerFail = 1, expected = M7_MPROBE_PREPARE;
    else if (!strcmp(argv[1], "sem")) semFail = 1, expected = M7_MPROBE_PREPARE;
    else if (!strcmp(argv[1], "stop")) stopFail = 1, expected = M7_MPROBE_STOP;
    else if (!strcmp(argv[1], "timer_stop")) timerStopFail = 1, expected = M7_MPROBE_STOP;
    else if (!strcmp(argv[1], "sleep")) sleepFail = 1, expected = M7_MPROBE_SLEEP;
    else if (!strcmp(argv[1], "dma")) dmaFault = 1, expected = M7_MPROBE_PROCESS;
    else if (!strcmp(argv[1], "mode")) wrongMode = 1, expected = M7_MPROBE_STATE;
    else if (!strcmp(argv[1], "readback")) wrongReadback = 1, expected = M7_MPROBE_CLEANUP;
    else if (!strcmp(argv[1], "tx")) touchedTx = 1, expected = M7_MPROBE_STATE;
    else if (!strcmp(argv[1], "timeout")) slow = 1, expected = M7_MPROBE_PROCESS;
    else if (!strncmp(argv[1], "allocation_", 11)) {
        i = (unsigned)atoi(argv[1] + 11); assert(i >= 1 && i <= 16); failAllocation = i; expected = M7_MPROBE_PREPARE;
    } else assert(0);
    assert(m7_mn_probe(&out) == expected && !out.clean && m7_plk_faulted());
    stops = ethStops; releases = timerReleases;
    assert(m7_mn_probe(&out) == M7_MPROBE_CONTEXT && ethStops == stops && timerReleases == releases);
    assert(!writes && ethStops <= 1 && timerReleases <= 1);
    printf("P3f REAL stack fault %s PASS, terminal retained; heap=%u ETH=%d timer=%d\n", argv[1], live, ethLease, timerLease);
    return 0;
}
