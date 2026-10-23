/* Same public headers as pinned P3g; no upstream, RTOS or hardware execution. */
#include <stddef.h>
#include <stdint.h>
#define M7_POWERLINK_NMT_PROBE 1
#define M7_POWERLINK_MN_PROBE 1
#define M7_POWERLINK_TIMER_PROBE 1
#define M7_POWERLINK_ETH_PROBE 1
#define M7_POWERLINK_EDRV_PROBE 1
#include "rk3572_powerlink_app.h"
#define OFF(type, field) ((uint32_t)offsetof(type, field))
_Static_assert(sizeof(M7PowerlinkSnapshot) == 1504, "P3g snapshot ABI");
_Static_assert(offsetof(M7PowerlinkSnapshot, nmtProbe) == 80, "P3g NMT cache offset");
_Static_assert(sizeof(M7NmtProbeResult) == 496 && sizeof(M7MnProbeResult) == 472, "P3g result ABI");
_Static_assert(sizeof(M7MnStatus) == 40 && sizeof(M7TimerHardware) == 96, "P3g nested ABI");
const uint32_t m7_nmt_layout[] = {
    sizeof(M7PowerlinkSnapshot), OFF(M7PowerlinkSnapshot, mn), OFF(M7PowerlinkSnapshot, nmtProbe),
    OFF(M7PowerlinkSnapshot, lifecycle), sizeof(M7NmtProbeResult), sizeof(M7MnProbeResult),
    OFF(M7NmtProbeResult, resetSubmitted), OFF(M7NmtProbeResult, reached), sizeof(M7MnStatus),
    OFF(M7MnStatus, nmtState), OFF(M7MnStatus, processes), OFF(M7MnProbeResult, timerIrqs),
    OFF(M7MnProbeResult, initialized), OFF(M7MnProbeResult, prepared), OFF(M7MnProbeResult, final),
    OFF(M7MnProbeResult, active) + OFF(M7EthHardware, mac),
    OFF(M7MnProbeResult, stopped) + OFF(M7EthHardware, mac),
    OFF(M7MnProbeResult, timerInitial), OFF(M7MnProbeResult, timerFinal), sizeof(M7TimerHardware),
    OFF(M7TimerHardware, level), OFF(M7TimerHardware, cntp), OFF(M7TimerHardware, cpuControl)
};
#ifdef M7_NATIVE_LAYOUT
#include <stdio.h>
int main(void)
{
    unsigned i;
    putchar('[');
    for (i = 0; i < sizeof(m7_nmt_layout) / sizeof(m7_nmt_layout[0]); ++i)
        printf("%s%u", i ? "," : "", m7_nmt_layout[i]);
    puts("]"); return 0;
}
#endif
