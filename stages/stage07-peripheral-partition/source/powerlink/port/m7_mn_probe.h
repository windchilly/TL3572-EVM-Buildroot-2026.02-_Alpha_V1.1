/* Explicit P3f full-stack GsOff lifecycle, not MN reset or network operation. */
#ifndef M7_MN_PROBE_H
#define M7_MN_PROBE_H
#include "m7_mn.h"
#include "m7_eth_probe.h"
#include "m7_timer_probe.h"
#define M7_MN_PROBE_LOOPS 128U
typedef struct {
    uint32_t result, clean, stage, stackError, loops;
    uint32_t leaseBefore, leaseAfter, timerBefore, timerAfter;
    uint32_t rx, tx, txDescriptors, dropped, rxErrors, txErrors, fatal;
    uint64_t timerIrqs, timerCallbacks;
    M7MnStatus initialized, prepared, final;
    M7EthHardware active, stopped;
    M7TimerHardware timerInitial, timerFinal;
} M7MnProbeResult;
enum { M7_MPROBE_OK, M7_MPROBE_CONTEXT, M7_MPROBE_INIT, M7_MPROBE_PREPARE,
       M7_MPROBE_PROCESS, M7_MPROBE_STATE, M7_MPROBE_STOP, M7_MPROBE_EXIT,
       M7_MPROBE_CLEANUP, M7_MPROBE_SLEEP };
uint32_t m7_mn_probe(M7MnProbeResult* out);
#endif
