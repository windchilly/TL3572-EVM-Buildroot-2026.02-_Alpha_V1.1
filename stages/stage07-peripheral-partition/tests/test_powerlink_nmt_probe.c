/* Real full stack, NMT/API/OD/EDRV/timers. Hardware and failure edges mocked. */
#define M7_MN_PROBE_TEST_MAIN GsOffRegressionMain
#define M7_NMT_PROBE_TEST 1
#include "test_powerlink_mn_probe.c"
#include "m7_nmt_probe.h"
static int resetFail, offFail, stalledReset, stalledOff, processFail;
static unsigned resetCommands, offCommands;
static uint32_t nmtTrace[16];
static unsigned traceCount;
tOplkError __real_nmtu_processEvent(const tEvent* event);
tOplkError __wrap_nmtu_processEvent(const tEvent* event)
{
    if (event->eventType == kEventTypeNmtStateChange) {
        assert(traceCount < 16);
        nmtTrace[traceCount++] = ((const tEventNmtStateChange*)event->eventArg.pEventArg)->newNmtState;
    }
    return __real_nmtu_processEvent(event);
}
tOplkError __real_oplk_execNmtCommand(tNmtEvent command);
uint32_t __real_m7_mn_process(void);
tOplkError __wrap_oplk_execNmtCommand(tNmtEvent command)
{
    assert(task == 1 && !isr && !masked);
    if (command == kNmtEventSwReset) { ++resetCommands; if (resetFail) return kErrorNoResource; }
    else { assert(command == kNmtEventSwitchOff); ++offCommands; if (offFail) return kErrorNoResource; }
    return __real_oplk_execNmtCommand(command);
}
uint32_t __wrap_m7_mn_process(void)
{
    if (processFail) return kErrorNoResource;
    if ((stalledReset && !offCommands) || (stalledOff && offCommands)) return kErrorOk;
    return __real_m7_mn_process();
}
int main(int argc, char** argv)
{
    M7NmtProbeResult out; uint32_t expected = 0; unsigned i, stops, releases, freed;
    assert(argc == 2 && m7_nmt_probe(NULL) == M7_MPROBE_CONTEXT);
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            static const uint32_t expectedTrace[] = {kNmtGsInitialising, kNmtGsResetApplication,
                kNmtGsResetCommunication, kNmtGsResetConfiguration, kNmtMsNotActive, kNmtGsOff};
            traceCount = 0;
            uint32_t rc = m7_nmt_probe(&out);
            if (rc) fprintf(stderr, "NMT probe rc=%u stack=%x stage=%u reached=%x state=%x loops=%u/%u events=%llu heap=%u\n",
                rc, out.lifecycle.stackError, out.lifecycle.stage, out.reached, out.lifecycle.final.nmtState,
                out.resetLoops, out.offLoops, (unsigned long long)out.lifecycle.final.events, live);
            assert(!rc && out.lifecycle.clean && out.lifecycle.stage == 6);
            assert(out.resetSubmitted && out.offSubmitted && out.reached == kNmtMsNotActive);
            assert(out.resetLoops && out.resetLoops <= 32 && out.offLoops && out.offLoops <= 32);
            assert(out.lifecycle.final.state == M7_MN_COLD && out.lifecycle.final.nmtState == kNmtGsOff);
            assert(!live && !sems && !m7_plk_owner() && !ethLease && !timerLease);
            assert(traceCount == 6 && !memcmp(nmtTrace, expectedTrace, sizeof(expectedTrace)));
            if (!i) printf("REAL NMT trace: %x -> %x -> %x -> %x -> %x -> %x; loops=%u/%u, time=%llums (MOCK time)\n",
                nmtTrace[0], nmtTrace[1], nmtTrace[2], nmtTrace[3], nmtTrace[4], nmtTrace[5], out.resetLoops, out.offLoops, (unsigned long long)now);
        }
        assert(resetCommands == 100 && offCommands == 100 && allocations == frees && !writes);
        printf("P3g 100 REAL NMT resets to NotActive/SwitchOff: alloc/free=%u, no TX/timer arm; hardware MOCKED\n", frees);
        return 0;
    }
    if (!strcmp(argv[1], "context")) {
        isr = 1; assert(m7_nmt_probe(&out) == M7_MPROBE_CONTEXT); isr = 0;
        masked = 1; assert(m7_nmt_probe(&out) == M7_MPROBE_CONTEXT); masked = 0;
        ethLease = 1; assert(m7_nmt_probe(&out) == M7_MPROBE_CONTEXT); ethLease = 0;
        assert(target_init() == kErrorOk && m7_nmt_probe(&out) == M7_MPROBE_CONTEXT);
        assert(!allocations && !resetCommands && !ethAcquires); return 0;
    }
    if (!strcmp(argv[1], "reset_command")) resetFail = 1, expected = M7_NPROBE_COMMAND;
    else if (!strcmp(argv[1], "off_command")) offFail = 1, expected = M7_NPROBE_COMMAND;
    else if (!strcmp(argv[1], "reset_timeout")) stalledReset = 1, expected = M7_NPROBE_TIMEOUT;
    else if (!strcmp(argv[1], "off_timeout")) stalledOff = 1, expected = M7_NPROBE_TIMEOUT;
    else if (!strcmp(argv[1], "process")) processFail = 1, expected = M7_MPROBE_PROCESS;
    else if (!strcmp(argv[1], "phy")) phyFail = 1, expected = M7_MPROBE_PREPARE;
    else if (!strcmp(argv[1], "stop")) stopFail = 1, expected = M7_MPROBE_STOP;
    else if (!strcmp(argv[1], "timer_stop")) timerStopFail = 1, expected = M7_MPROBE_STOP;
    else if (!strcmp(argv[1], "sleep")) sleepFail = 1, expected = M7_MPROBE_SLEEP;
    else if (!strcmp(argv[1], "dma")) dmaFault = 1, expected = M7_MPROBE_PROCESS;
    else if (!strcmp(argv[1], "mode")) wrongMode = 1, expected = M7_NPROBE_STATE;
    else if (!strcmp(argv[1], "readback")) wrongReadback = 1, expected = M7_MPROBE_CLEANUP;
    else if (!strcmp(argv[1], "tx")) touchedTx = 1, expected = M7_NPROBE_STATE;
    else if (!strcmp(argv[1], "wall_timeout")) slow = 1, expected = M7_NPROBE_TIMEOUT;
    else if (!strncmp(argv[1], "allocation_", 11)) {
        i = (unsigned)atoi(argv[1] + 11); assert(i >= 17 && i <= 25); failAllocation = i;
        expected = M7_MPROBE_PROCESS;
    } else assert(0);
    assert(m7_nmt_probe(&out) == expected && !out.lifecycle.clean && m7_plk_faulted());
    stops = ethStops; releases = timerReleases; freed = frees;
    assert(m7_nmt_probe(&out) == M7_MPROBE_CONTEXT && ethStops == stops && timerReleases == releases && frees == freed);
    assert(!writes && ethStops <= 1 && timerReleases <= 1);
    printf("P3g REAL stack negative %s PASS, terminal retained; heap=%u ETH=%d timer=%d\n", argv[1], live, ethLease, timerLease);
    return 0;
}
