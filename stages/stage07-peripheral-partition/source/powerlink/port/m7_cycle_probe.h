/* P3j fixed one-shot diagnostic. Pure types; NO continuous MN/run API.
 * SOFTWARE thresholds, not proven RTOS/industrial deadlines. Hardware needs
 * new isolated ETH2/CNTP authorization and a separately reviewed runner.
 */
#ifndef M7_CYCLE_PROBE_H
#define M7_CYCLE_PROBE_H
#include "m7_mn_probe.h"
#define M7_CYCLE_ABI 1U
#define M7_CYCLE_MAX_LOOPS 4000000U
#define M7_CYCLE_TOTAL_MS 8000U
#define M7_CYCLE_NMT_MS 3000U
#define M7_CYCLE_RUN_MS 100U
#define M7_CYCLE_RUN_TX 256U
#define M7_CYCLE_TOTAL_TX 1024U
#define M7_CYCLE_PENDING_US 2000U
#define M7_CYCLE_IDLE_US 10000U
#define M7_CYCLE_MAX_LATE_US 500U
#define M7_CYCLE_DRAIN_US 5000U
#define M7_CYCLE_QUIET_US 1000U
enum { M7_CYCLE_CONTEXT=0x300, M7_CYCLE_CONFIG, M7_CYCLE_PROCESS,
    M7_CYCLE_BUDGET, M7_CYCLE_STATE, M7_CYCLE_PENDING, M7_CYCLE_IDLE,
    M7_CYCLE_TIMER, M7_CYCLE_IO, M7_CYCLE_DRAIN, M7_CYCLE_COMMAND,
    M7_CYCLE_STOP, M7_CYCLE_EXIT, M7_CYCLE_CLEANUP };
typedef struct {
    uint32_t abi, bytes;
    M7MnProbeResult lifecycle;
    uint32_t resetSubmitted, offSubmitted, reached, stopCycleCalls;
    uint32_t owner, pending, maxPending, pendingAtStop;
    uint32_t txBeforeRun, txAtStop, runLoops, drainLoops, offLoops;
    uint32_t contextValid, watchdogTrips, frequency;
    uint64_t startCounter, endCounter, runCounter, lastTxCounter, pendingCounter;
    uint64_t maxGapTicks, maxLateTicks, skippedPeriods;
} M7CycleProbeResult;
/* May consume CPU5 for a bounded interval; checks only after calls return.
 * Cannot preempt a hung stack call. Every invocation, including success, is
 * one-shot until reboot. Unknown/fault retains all live resources. */
uint32_t m7_cycle_probe(M7CycleProbeResult* out);
#endif
