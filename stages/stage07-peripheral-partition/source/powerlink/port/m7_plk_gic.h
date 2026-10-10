/* GICv2 NS-EL1 preflight. IGROUPR is RAZ/WI to Non-secure accesses when
 * SecurityExtn=1 (Arm IHI0048B 4.3.4); zero cannot prove Group0 ownership.
 * No security/group/global writes. Hardware enable readback remains mandatory. */
#ifndef M7_PLK_GIC_H
#define M7_PLK_GIC_H
#include <stdint.h>
static inline int m7_plk_gic_usable(uint32_t typer, uint32_t group,
    uint32_t cpuControl, uint32_t enabled, uint32_t pending, uint32_t active, uint32_t config)
{
    if ((enabled | pending | active) & (1U << 30) || (config & (1U << 29))) return 0;
    if (typer & (1U << 10)) return (cpuControl & 1U) != 0; /* NS EnableGrp1 */
    return (cpuControl & (1U << ((group >> 30) & 1U))) != 0;
}
#endif
