/* UP2-only P2 platform: CNTP/PPI30, RTOS semaphores and owned cache lines.
 * CNTV/PPI27 (OS tick), other PPIs, shared GIC config and CRU are untouched.
 * The pinned generic PRT_HwiDelete/Disable PPI path uses GICR addresses: do not
 * use it on this GICv2 BSP. Reserve our handler until reboot; stop masks only
 * PPI30. No controller-global initialization/reset and no Ethernet access. */
#include "prt_config.h"
#include "prt_hwi.h"
#include "prt_task.h"
#include "prt_tick.h"
#include "prt_sem.h"
#include "prt_asm_cpu_external.h"
#include "cpu_config.h"
#include "m7_plk_platform.h"
#include "m7_plk_cache.h"
#include "m7_plk_gic.h"
#ifdef M7_POWERLINK_TIMER_PROBE
#include "m7_timer_probe.h"
static volatile uint64_t diagDeadline, diagInterrupts, diagMaxLate;
#endif
#if MCS_CLIENT_CPU_ID != 5 || OS_GIC_VER != 2
#error "POWERLINK platform requires the pinned UP2 GICv2 configuration"
#endif
#if defined(OS_OPTION_SMP)
#error "P2 context check is for the pinned non-SMP UP2 kernel only"
#endif
/* One explicitly pinned private ABI: flags from prt_asm_cpu_external.h.
 * Reject ALL ISR/tick/system/exception contexts, not only our timer ISR. */
extern U32 g_uniFlag;
#define PLK_PPI 30U
#define PLK_BIT (1U << PLK_PPI)
#define PLK_GICD 0x2a601000ULL
static int reserved, running;
static uint8_t savedPriority;
static uint32_t readGic(unsigned offset) { return *(volatile uint32_t*)(PLK_GICD + offset); }
static void writeGic(unsigned offset, uint32_t value)
{
    *(volatile uint32_t*)(PLK_GICD + offset) = value;
    __asm__ volatile("dsb sy\n\tisb" ::: "memory");
}
int m7_plk_in_interrupt(void)
{
    return (g_uniFlag & (OS_FLG_HWI_ACTIVE | OS_FLG_TICK_ACTIVE |
        OS_FLG_SYS_ACTIVE | OS_FLG_EXC_ACTIVE)) != 0;
}
int m7_plk_task_id(uint32_t* id) { return id && !m7_plk_in_interrupt() && PRT_TaskSelf(id) == OS_OK; }
int m7_plk_irq_enabled(void)
{
    uint64_t daif;
    __asm__ volatile("mrs %0, daif" : "=r"(daif));
    return !(daif & 0x80U);
}
uintptr_t m7_plk_irq_save(void) { return PRT_HwiLock(); }
void m7_plk_irq_restore(uintptr_t state) { PRT_HwiRestore(state); }
uint64_t m7_plk_milliseconds(void)
{
    uint64_t ticks = PRT_TickGetCount();
    return (ticks / OS_TICK_PER_SECOND) * 1000U +
        (ticks % OS_TICK_PER_SECOND) * 1000U / OS_TICK_PER_SECOND;
}
int m7_plk_sleep(uint32_t ms)
{
    uint64_t daif, ticks = ((uint64_t)ms * OS_TICK_PER_SECOND + 999U) / 1000U;
    __asm__ volatile("mrs %0, daif" : "=r"(daif));
    if (m7_plk_in_interrupt() || (daif & 0x80U) || ticks > UINT32_MAX) return 0;
    return !ticks || PRT_TaskDelay((uint32_t)ticks) == OS_OK;
}
int m7_plk_sem_create(uint16_t* handle) { return PRT_SemCreate(1U, handle) == OS_OK; }
int m7_plk_sem_take(uint16_t handle) { return PRT_SemPend(handle, OS_NO_WAIT) == OS_OK; }
int m7_plk_sem_give(uint16_t handle) { return PRT_SemPost(handle) == OS_OK; }
int m7_plk_sem_delete(uint16_t handle) { return PRT_SemDelete(handle) == OS_OK; }
int m7_plk_cache(const void* address, size_t length, int invalidate)
{
    uintptr_t begin = (uintptr_t)address, end, line, cursor;
    int range;
    uint64_t ctr;
    if (!length) return 1;
    range = m7_plk_cache_range(begin, length);
    if (!range) return 0;
    end = begin + length;
    if (range == 2) {
        /* This exact DMA aperture is mapped Normal-NC, no cacheable alias. */
        __asm__ volatile("dsb sy" ::: "memory"); return 1;
    }
    /* CAL/heap/static memory must belong to UP2's cacheable 8 MiB image. */
    __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
    line = (uintptr_t)4U << ((ctr >> 16) & 15U);
    cursor = begin & ~(line - 1U);
    __asm__ volatile("dsb sy" ::: "memory");
    for (; cursor < end; cursor += line) {
        /* Local CAL only: CIVAC preserves dirty partial-line neighbors. Not
         * a substitute for the noncacheable GMAC DMA ownership protocol. */
        if (invalidate) __asm__ volatile("dc civac, %0" :: "r"(cursor) : "memory");
        else __asm__ volatile("dc cvac, %0" :: "r"(cursor) : "memory");
    }
    __asm__ volatile("dsb sy" ::: "memory");
    return 1;
}
uint64_t m7_plk_timer_now(void)
{
    uint64_t now;
    __asm__ volatile("isb\n\tmrs %0, cntpct_el0" : "=r"(now) :: "memory");
    return now;
}
void m7_plk_timer_mask(void)
{
    uint64_t control = 2U; /* ENABLE=0, IMASK=1 */
    __asm__ volatile("msr cntp_ctl_el0, %0\n\tisb" :: "r"(control) : "memory");
}
void m7_plk_timer_arm(uint64_t deadline)
{
    uint64_t control = 1U;
#ifdef M7_POWERLINK_TIMER_PROBE
    diagDeadline = deadline;
#endif
    __asm__ volatile("msr cntp_cval_el0, %0\n\tmsr cntp_ctl_el0, %1\n\tisb"
        :: "r"(deadline), "r"(control) : "memory");
}
static void timerIsr(uintptr_t argument)
{
    (void)argument;
#ifdef M7_POWERLINK_TIMER_PROBE
    if (running) {
        uint64_t now = m7_plk_timer_now();
        uint64_t late = now - diagDeadline;
        ++diagInterrupts;
        if (late > diagMaxLate) diagMaxLate = late;
    }
#endif
    if (running) m7_hrestimer_interrupt();
    else m7_plk_timer_mask();
}
int m7_plk_timer_acquire(uint32_t* frequency)
{
    uint64_t affinity, level, control, freq;
    uintptr_t state;
    if (!frequency || m7_plk_in_interrupt() || running) return 0;
    __asm__ volatile("mrs %0, mpidr_el1\n\tmrs %1, currentel" : "=r"(affinity), "=r"(level));
    if ((affinity & 0xffffffU) != 0x101U || level != 4U) return 0;
    /* EL2 access permission cannot be proved at EL1: must be verified before
     * P3 deployment. A trap here is not a supported fallback/claimed success. */
    __asm__ volatile("mrs %0, cntp_ctl_el0\n\tmrs %1, cntfrq_el0" : "=r"(control), "=r"(freq));
    if ((control & 1U) || !freq || freq > 1000000000U) return 0;
    state = PRT_HwiLock();
    if (!m7_plk_gic_usable(readGic(4), readGic(0x80),
        *(volatile uint32_t*)(PLK_GICD + 0x1000U),
        readGic(0x100), readGic(0x200), readGic(0x300), readGic(0xc04))) {
        PRT_HwiRestore(state); return 0;
    }
    if (!reserved) {
        if (PRT_HwiSetAttr(PLK_PPI, 10U, OS_HWI_MODE_ENGROSS) != OS_OK ||
            PRT_HwiCreate(PLK_PPI, timerIsr, 0) != OS_OK) {
            PRT_HwiRestore(state); return 0;
        }
        reserved = 1;
    }
    savedPriority = *(volatile uint8_t*)(PLK_GICD + 0x400U + PLK_PPI);
    m7_plk_timer_mask();
    *(volatile uint8_t*)(PLK_GICD + 0x400U + PLK_PPI) = 0xa0U;
    writeGic(0x280, PLK_BIT); running = 1;
    writeGic(0x100, PLK_BIT);
    if (!(readGic(0x100) & PLK_BIT) ||
        *(volatile uint8_t*)(PLK_GICD + 0x400U + PLK_PPI) != 0xa0U) {
        writeGic(0x180, PLK_BIT); writeGic(0x280, PLK_BIT);
        if ((readGic(0x100) | readGic(0x300)) & PLK_BIT) {
            /* Admit a faulted lease so hrestimer retains ownership if release
             * cannot prove silence. Never return a false unowned failure. */
            *frequency = 0; PRT_HwiRestore(state); return 1;
        }
        running = 0;
        *(volatile uint8_t*)(PLK_GICD + 0x400U + PLK_PPI) = savedPriority;
        PRT_HwiRestore(state); return 0;
    }
    *frequency = (uint32_t)freq;
    PRT_HwiRestore(state); return 1;
}
int m7_plk_timer_release(void)
{
    uintptr_t state;
    if (m7_plk_in_interrupt() || !running) return 0;
    state = PRT_HwiLock();
    m7_plk_timer_mask(); writeGic(0x180, PLK_BIT); writeGic(0x280, PLK_BIT);
    if ((readGic(0x100) | readGic(0x300)) & PLK_BIT) {
        PRT_HwiRestore(state); return 0; /* retain running/lease on unsafe stop */
    }
    *(volatile uint8_t*)(PLK_GICD + 0x400U + PLK_PPI) = savedPriority;
    running = 0; PRT_HwiRestore(state);
    return 1; /* reservation remains; the handler is dormant until next init */
}
#ifdef M7_POWERLINK_TIMER_PROBE
int m7_timer_diag_reset(void)
{
    uintptr_t lock;
    if (m7_plk_in_interrupt() || !m7_plk_irq_enabled() || running) return 0;
    lock = PRT_HwiLock(); diagDeadline = diagInterrupts = diagMaxLate = 0;
    PRT_HwiRestore(lock); return 1;
}
int m7_timer_diag_snapshot(M7TimerHardware* out)
{
    uint64_t level, frequency, cntp, cntv;
    uintptr_t lock;
    if (!out || m7_plk_in_interrupt() || !m7_plk_irq_enabled()) return 0;
    lock = PRT_HwiLock();
    __asm__ volatile("mrs %0, currentel\n\tmrs %1, cntfrq_el0\n\tmrs %2, cntp_ctl_el0\n\tmrs %3, cntv_ctl_el0"
        : "=r"(level), "=r"(frequency), "=r"(cntp), "=r"(cntv));
    out->level = (uint32_t)level; out->frequency = (uint32_t)frequency;
    out->cntp = (uint32_t)cntp; out->cntv = (uint32_t)cntv;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(out->affinity));
    out->counter = m7_plk_timer_now(); out->ticks = PRT_TickGetCount();
    out->enabled = readGic(0x100); out->pending = readGic(0x200);
    out->active = readGic(0x300); out->group = readGic(0x80); out->config = readGic(0xc04);
    out->priority30 = *(volatile uint8_t*)(PLK_GICD + 0x400U + 30U);
    out->priority27 = *(volatile uint8_t*)(PLK_GICD + 0x400U + 27U);
    out->typer = readGic(4); out->cpuControl = *(volatile uint32_t*)(PLK_GICD + 0x1000U);
    out->interrupts = diagInterrupts; out->maxIrqLate = diagMaxLate;
    PRT_HwiRestore(lock); return 1;
}
#endif
