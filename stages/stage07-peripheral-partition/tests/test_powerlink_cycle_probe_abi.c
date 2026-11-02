#define M7_POWERLINK_TIMER_PROBE 1
#define M7_POWERLINK_ETH_PROBE 1
#define M7_POWERLINK_EDRV_PROBE 1
#define M7_POWERLINK_MN_PROBE 1
#define M7_POWERLINK_NMT_PROBE 1
#define M7_POWERLINK_CYCLE_PROBE 1
#include <stddef.h>
#include "rk3572_powerlink_app.h"
const uint32_t m7_cycle_layout[]={sizeof(M7CycleProbeResult),offsetof(M7CycleProbeResult,lifecycle),
    offsetof(M7CycleProbeResult,resetSubmitted),offsetof(M7CycleProbeResult,owner),offsetof(M7CycleProbeResult,runLoops),
    offsetof(M7CycleProbeResult,contextValid),offsetof(M7CycleProbeResult,startCounter),offsetof(M7CycleProbeResult,pendingCounter),
    offsetof(M7CycleProbeResult,maxGapTicks),sizeof(M7PowerlinkSnapshot)};
#ifdef M7_NATIVE_LAYOUT
#include <stdio.h>
int main(void)
{
    size_t i;putchar('[');
    for(i=0;i<sizeof(m7_cycle_layout)/sizeof(m7_cycle_layout[0]);++i)printf("%s%u",i?",":"",m7_cycle_layout[i]);
    puts("]");return 0;
}
#endif
