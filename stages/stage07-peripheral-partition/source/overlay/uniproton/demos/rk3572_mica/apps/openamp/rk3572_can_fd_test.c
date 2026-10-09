/* M7 CAN1/CAN3 CAN FD smoke test: owned resources and IRQ data path.
 * Linux must release the device/IRQ first. Shared PLLs, bus roots and GIC
 * group/config words are untouched. No hardware FIFO polling in task context.
 */
#include "prt_config.h"
#include "prt_hwi.h"
#include "prt_task.h"
#include "prt_typedef.h"
#include "cpu_config.h"
#include "test.h"
#include "rk3572_can_fd_codec.h"

#define CRU_GATE 0x2609082CULL
#define CRU_RESET 0x26090A2CULL
#if (MCS_CLIENT_CPU_ID == 4)
#define CAN_BASE 0x2AB10000ULL
#define CAN_INTID 185U
#define CRU_SELECT 0x26090404ULL
#define CRU_MASK 0x0600U
#define IOC_MUX 0x2608608CULL
#define IOC_MASK 0xFF00U
#define IOC_VALUE 0xDD00U
#define EXPECTED_MPIDR 0x100U
#elif (MCS_CLIENT_CPU_ID == 5)
#define CAN_BASE 0x2AB30000ULL
#define CAN_INTID 187U
#define CRU_SELECT 0x26090408ULL
#define CRU_MASK 0x6000U
#define IOC_MUX 0x2608203CULL
#define IOC_MASK 0x0FF0U
#define IOC_VALUE 0x0DD0U
#define EXPECTED_MPIDR 0x101U
#else
#error "CAN IRQ test supports CPU4/CPU5 only"
#endif
#define CAN_MODE 0x000U
#define CAN_CMD 0x004U
#define CAN_STATE 0x008U
#define CAN_INT 0x00CU
#define CAN_INT_MASK 0x010U
#define CAN_NBTP 0x100U
#define CAN_DBTP 0x104U
#define CAN_TDCR 0x108U
#define CAN_BRS_CFG 0x10CU
#define CAN_ERROR_CODE 0x900U
#define CAN_TXFIC 0x200U
#define CAN_TXID 0x204U
#define CAN_TXDAT0 0x208U
#define CAN_RXFRD 0x400U
#define CAN_STR_CTL 0x600U
#define CAN_STR_STATE 0x604U
#define CAN_STR_WTM 0x60CU
#define CAN_ATF0 0x700U
#define CAN_ATFM0 0x714U
#define CAN_ATF_DLC 0x728U
#define CAN_ATF_CTL 0x72CU
#define CAN_AUTO_RETX_CFG 0x808U
#define CAN_BUSOFFRCY_CFG 0x830U
#define CAN_BUSOFF_RCY_THR 0x834U
#define CAN_RXERRORCNT 0x910U
#define CAN_TXERRORCNT 0x914U
#define TX_FINISH (1U << 1)
#define RX_EVENTS ((1U << 0) | (1U << 7) | (1U << 15) | (1U << 17))
#define STAGE_FRAMES 1000U
#define FRAMES (3U * STAGE_FRAMES)
#if (M7_CAN_FD_PROFILE == 0)
#define BRS_ENABLED 0U
#define DATA_BTP RK_CAN_FD_DBTP2
#define TDC_VALUE 0U
#elif (M7_CAN_FD_PROFILE == 2)
#define BRS_ENABLED 1U
#define DATA_BTP RK_CAN_FD_DBTP2
#define TDC_VALUE 0U
#elif (M7_CAN_FD_PROFILE == 4)
#define BRS_ENABLED 1U
#define DATA_BTP RK_CAN_FD_DBTP4
#define TDC_VALUE RK_CAN_FD_TDCR4
#else
#error "CAN FD profile must be 0, 2 or 4"
#endif
#define WAIT_TICKS 2000U

struct CanFrame { U32 id, info; U8 len; U8 data[64]; };
struct CanIrqState {
    volatile U32 irqCount, txIrq, rxIrq, errorFlags, overflow, wrongCpu;
    volatile U32 txDone, rxReady, statusOr, rxFd, rxBrs;
    struct CanFrame received;
    U32 txCount, rxCount, txBytes, rxBytes, lastInfo;
    U8 target, savedTarget, savedPriority;
};
static struct CanIrqState g_can;

static U32 Read32(U64 address) { return *(volatile U32 *)(uintptr_t)address; }
static void Write32(U64 address, U32 value)
{
    *(volatile U32 *)(uintptr_t)address = value;
    __asm__ volatile("dsb sy" ::: "memory");
}
static void WriteByte(U64 address, U8 value)
{
    *(volatile U8 *)(uintptr_t)address = value;
    __asm__ volatile("dsb sy" ::: "memory");
}
static U32 CanRead(U32 offset) { return Read32(CAN_BASE + offset); }
static void CanWrite(U32 offset, U32 value) { Write32(CAN_BASE + offset, value); }
static void Hiword(U64 address, U32 mask, U32 value)
{
    Write32(address, (mask << 16) | (value & mask));
}
static U32 CpuAffinity(void)
{
    U64 value;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(value));
    return (U32)value & 0xFFFFFFU;
}
static void DisableSpi(void)
{
    Write32(GIC_DIST_BASE + 0x180U + (CAN_INTID / 32U) * 4U, 1U << (CAN_INTID % 32U));
}
static U32 InitializeResources(void)
{
    PRT_Printf("[can-irq] UP%u before gate=0x%x reset=0x%x select=0x%x\n",
               MCS_CLIENT_CPU_ID - 3U, Read32(CRU_GATE), Read32(CRU_RESET), Read32(CRU_SELECT));
    DisableSpi();
    Hiword(CRU_GATE, CRU_MASK, 0U);
    Hiword(CRU_RESET, CRU_MASK, CRU_MASK);
    (void)PRT_TaskDelay(1U);
    /* System GPLL is fixed at 1188 MHz; own divider /4 gives 297 MHz. */
    Hiword(CRU_SELECT, 0x3F80U, 3U << 7);
    Hiword(IOC_MUX, IOC_MASK, IOC_VALUE);
    Hiword(CRU_RESET, CRU_MASK, 0U);
    (void)PRT_TaskDelay(1U);
    if ((Read32(CRU_GATE) & CRU_MASK) || (Read32(CRU_RESET) & CRU_MASK) ||
        ((Read32(CRU_SELECT) & 0x3F80U) != (3U << 7)) ||
        ((Read32(IOC_MUX) & IOC_MASK) != IOC_VALUE)) { return 10U; }
    return 0U;
}
static void CanIsr(uintptr_t argument)
{
    U32 status, index, info, word;
    (void)argument;
    g_can.irqCount++;
    if (CpuAffinity() != EXPECTED_MPIDR) { g_can.wrongCpu++; }
    status = CanRead(CAN_INT);
    g_can.statusOr |= status;
    g_can.errorFlags |= status & ~(TX_FINISH | RX_EVENTS);
    if (status & TX_FINISH) {
        CanWrite(CAN_CMD, 0U); g_can.txIrq++; g_can.txDone = 1U;
    }
    /* Only the ISR consumes fixed 18-word hardware FIFO records. */
    while (((CanRead(CAN_STR_STATE) >> 8) & 0x1FFU) >= 18U) {
        struct CanFrame frame = {0};
        info = CanRead(CAN_RXFRD); frame.id = CanRead(CAN_RXFRD) & 0x7FFU;
        frame.info = info; frame.len = RkCanFdDlcToLength((U8)((info >> 24) & 15U));
        if (info & (1U << 21)) { g_can.rxFd++; }
        if (info & (1U << 20)) { g_can.rxBrs++; }
        for (index = 0U; index < 16U; index++) {
            word = CanRead(CAN_RXFRD);
            RkCanFdUnpackWord(word, &frame.data[index * 4U]);
        }
        g_can.rxIrq++;
        if (g_can.rxReady || !frame.len || frame.len > 64U) { g_can.overflow++; }
        else { g_can.received = frame; g_can.rxReady = 1U; }
    }
    CanWrite(CAN_INT, status);
}
static U32 InitializeController(void)
{
    U32 ret, index;
    U64 priority = GIC_DIST_BASE + 0x400U + CAN_INTID;
    U64 target = GIC_DIST_BASE + 0x800U + CAN_INTID;
    g_can.savedPriority = *(volatile U8 *)(uintptr_t)priority;
    g_can.savedTarget = *(volatile U8 *)(uintptr_t)target;
    /* ITARGETSR0 is banked: discover this CPU's actual target bit. */
    g_can.target = *(volatile U8 *)(uintptr_t)(GIC_DIST_BASE + 0x800U);
    if ((CpuAffinity() != EXPECTED_MPIDR) || !g_can.target ||
        ((g_can.target & (g_can.target - 1U)) != 0U)) { return 11U; }
    ret = PRT_HwiSetAttr(CAN_INTID, 10U, OS_HWI_MODE_ENGROSS);
    if (ret) { return ret; }
    ret = PRT_HwiCreate(CAN_INTID, CanIsr, 0U);
    if (ret) { return ret; }
    /* Register with the OS, then use GICv2 byte/W1S writes for this SPI. */
    WriteByte(priority, 0xA0U); WriteByte(target, g_can.target);
    Write32(GIC_DIST_BASE + 0x280U + (CAN_INTID / 32U) * 4U, 1U << (CAN_INTID % 32U));
    CanWrite(CAN_MODE, 0U); CanWrite(CAN_INT_MASK, 0xFFFFFFFFU); CanWrite(CAN_INT, 0xFFFFFFFFU);
    for (index = 0U; index < 5U; index++) {
        CanWrite(CAN_ATF0 + index * 4U, 0U); CanWrite(CAN_ATFM0 + index * 4U, 0x7FFFU);
    }
    CanWrite(CAN_ATF_DLC, 0U); CanWrite(CAN_ATF_CTL, 0U);
    CanWrite(CAN_STR_CTL, 0x108U);
    /* One frame triggers watermark IRQ; RX_FINISH remains masked as in vendor code. */
    CanWrite(CAN_STR_WTM, 18U);
    /* Bounded retries: fail fast on a missing ACK or incompatible peer. */
    CanWrite(CAN_AUTO_RETX_CFG, 1U | 2U | (100U << 3));
    CanWrite(CAN_BUSOFFRCY_CFG, (1U << 8) | 4U); CanWrite(CAN_BUSOFF_RCY_THR, 0x3D0900U);
    /* 297 MHz: nominal 500 kbit/s; data about 2.007/4.014 Mbit/s.
     * Data timing/BRS split and TDC follow Rockchip's CAN FD driver.
     */
    CanWrite(CAN_NBTP, RK_CAN_FD_NBTP); CanWrite(CAN_DBTP, DATA_BTP);
    CanWrite(CAN_TDCR, TDC_VALUE); CanWrite(CAN_BRS_CFG, RK_CAN_FD_BRS_CFG);
    if (CanRead(CAN_NBTP) != RK_CAN_FD_NBTP || CanRead(CAN_DBTP) != DATA_BTP ||
        CanRead(CAN_TDCR) != TDC_VALUE || CanRead(CAN_BRS_CFG) != RK_CAN_FD_BRS_CFG) { return 13U; }
    PRT_Printf("[can-fd] UP%u config profile=%u nbtp=0x%x dbtp=0x%x tdcr=0x%x brscfg=0x%x\n",
               MCS_CLIENT_CPU_ID - 3U, M7_CAN_FD_PROFILE, CanRead(CAN_NBTP), CanRead(CAN_DBTP),
               CanRead(CAN_TDCR), CanRead(CAN_BRS_CFG));
    Write32(GIC_DIST_BASE + 0x100U + (CAN_INTID / 32U) * 4U, 1U << (CAN_INTID % 32U));
    CanWrite(CAN_INT_MASK, 1U); CanWrite(CAN_MODE, 1U);
    PRT_Printf("[can-irq] UP%u ready mpidr=0x%x intid=%u target=0x%x nbtp=0x%x\n",
               MCS_CLIENT_CPU_ID - 3U, CpuAffinity(), CAN_INTID, g_can.target, CanRead(CAN_NBTP));
    return (CanRead(CAN_MODE) & 1U) ? 0U : 12U;
}
static void Fill(struct CanFrame *frame, U32 id, U8 marker, U32 sequence)
{
    U32 index;
    frame->id = id; frame->len = (U8)(16U << (sequence / STAGE_FRAMES)); frame->data[0] = marker;
    frame->data[1] = (U8)(sequence >> 24); frame->data[2] = (U8)(sequence >> 16);
    frame->data[3] = (U8)(sequence >> 8); frame->data[4] = (U8)sequence;
    frame->data[5] = M7_CAN_FD_PROFILE;
    for (index = 6U; index < frame->len; index++) {
        frame->data[index] = (U8)(sequence * 13U + index * 7U + (marker ^ 0x5AU));
    }
}
static U32 Matches(const struct CanFrame *frame, U32 id, U8 marker, U32 sequence)
{
    struct CanFrame expected; U32 index;
    Fill(&expected, id, marker, sequence);
    if (frame->id != expected.id || frame->len != expected.len ||
        !RkCanFdMatchesRxFlags(frame->info, BRS_ENABLED)) { return 0U; }
    for (index = 0U; index < expected.len; index++) {
        if (frame->data[index] != expected.data[index]) { return 0U; }
    }
    return 1U;
}
static U32 Transmit(const struct CanFrame *frame)
{
    U32 index, ticks, word;
    g_can.txDone = 0U; CanWrite(CAN_INT, TX_FINISH);
    CanWrite(CAN_TXID, frame->id); CanWrite(CAN_TXFIC, RkCanFdTxInfo(frame->len, BRS_ENABLED));
    for (index = 0U; index < (U32)frame->len / 4U; index++) {
        word = RkCanFdPackWord(&frame->data[index * 4U]);
        CanWrite(CAN_TXDAT0 + index * 4U, word);
    }
    CanWrite(CAN_CMD, (1U << 16) | 1U);
    for (ticks = 0U; ticks < WAIT_TICKS; ticks++) {
        if (g_can.errorFlags || g_can.overflow || g_can.wrongCpu) { return 20U; }
        if (g_can.txDone) { g_can.txCount++; g_can.txBytes += frame->len; return 0U; }
        (void)PRT_TaskDelay(1U);
    }
    return 21U;
}
static U32 Receive(struct CanFrame *frame, U32 timeout)
{
    U32 ticks;
    for (ticks = 0U; ticks < timeout; ticks++) {
        if (g_can.errorFlags || g_can.overflow || g_can.wrongCpu) { return 22U; }
        if (g_can.rxReady) {
            uintptr_t lock = PRT_HwiLock();
            *frame = g_can.received; g_can.rxReady = 0U;
            PRT_HwiRestore(lock); g_can.rxCount++; g_can.rxBytes += frame->len;
            g_can.lastInfo = frame->info; return 0U;
        }
        (void)PRT_TaskDelay(1U);
    }
    return 23U;
}
static U32 RunPair(void)
{
    struct CanFrame request = {0}, response = {0}; U32 sequence, ret;
#if (MCS_CLIENT_CPU_ID == 4)
    (void)PRT_TaskDelay(1000U);
#endif
    for (sequence = 0U; sequence < FRAMES; sequence++) {
#if (MCS_CLIENT_CPU_ID == 4)
        Fill(&request, 0x321U, (U8)'A', sequence); ret = Transmit(&request);
        if (!ret) { ret = Receive(&response, WAIT_TICKS); }
        if (!ret && !Matches(&response, 0x456U, (U8)'B', sequence)) { ret = 24U; }
#else
        ret = Receive(&request, sequence ? WAIT_TICKS : 30000U);
        if (!ret && !Matches(&request, 0x321U, (U8)'A', sequence)) { ret = 25U; }
        if (!ret) { Fill(&response, 0x456U, (U8)'B', sequence); ret = Transmit(&response); }
#endif
        if (ret) {
            PRT_Printf("[can-fd] UP%u fail seq=%u rc=%u int=0x%x fifo=0x%x ec=0x%x rxinfo=0x%x\n",
                       MCS_CLIENT_CPU_ID - 3U, sequence, ret, CanRead(CAN_INT), CanRead(CAN_STR_STATE),
                       CanRead(CAN_ERROR_CODE), g_can.lastInfo);
            return ret;
        }
        if ((sequence + 1U) % STAGE_FRAMES == 0U) {
            PRT_Printf("[can-fd] UP%u stage=%u len=%u profile=%u tx=%u rx=%u rxinfo=0x%x\n",
                       MCS_CLIENT_CPU_ID - 3U, (sequence + 1U) / STAGE_FRAMES,
                       16U << (sequence / STAGE_FRAMES), M7_CAN_FD_PROFILE,
                       g_can.txCount, g_can.rxCount, g_can.lastInfo);
        }
    }
    return 0U;
}
U32 Rk3572CanDirectTest(void)
{
    U32 ret = InitializeResources(), initialized = 0U;
    if (!ret) {
        initialized = 1U; ret = InitializeController();
        if (!ret) { ret = RunPair(); }
        CanWrite(CAN_INT_MASK, 0xFFFFFFFFU); CanWrite(CAN_MODE, 0U);
    }
    DisableSpi();
    Write32(GIC_DIST_BASE + 0x280U + (CAN_INTID / 32U) * 4U, 1U << (CAN_INTID % 32U));
    if (initialized) {
        WriteByte(GIC_DIST_BASE + 0x800U + CAN_INTID, g_can.savedTarget);
        WriteByte(GIC_DIST_BASE + 0x400U + CAN_INTID, g_can.savedPriority);
    }
    if (!ret && (g_can.txIrq != FRAMES || g_can.rxIrq != FRAMES ||
                  g_can.errorFlags || g_can.overflow || g_can.wrongCpu || g_can.rxFd != FRAMES ||
                  g_can.rxBrs != (BRS_ENABLED ? FRAMES : 0U))) { ret = 26U; }
    PRT_Printf("[can-irq] UP%u counts irq=%u txirq=%u rxirq=%u err=0x%x overflow=%u wrongcpu=%u target=0x%x status=0x%x\n",
               MCS_CLIENT_CPU_ID - 3U, g_can.irqCount, g_can.txIrq, g_can.rxIrq,
               g_can.errorFlags, g_can.overflow, g_can.wrongCpu, g_can.target, g_can.statusOr);
    PRT_Printf("[can-fd] UP%u %s profile=%u tx=%u rx=%u txbytes=%u rxbytes=%u rxfd=%u rxbrs=%u rc=%u\n",
               MCS_CLIENT_CPU_ID - 3U, ret ? "FAIL" : "PASS", M7_CAN_FD_PROFILE,
               g_can.txCount, g_can.rxCount, g_can.txBytes, g_can.rxBytes, g_can.rxFd, g_can.rxBrs, ret);
    PRT_Printf("[can] UP%u direct %s tx=%u rx=%u txerr=%u rxerr=%u state=0x%x rc=%u\n",
               MCS_CLIENT_CPU_ID - 3U, ret ? "FAIL" : "PASS", g_can.txCount, g_can.rxCount,
               initialized ? CanRead(CAN_TXERRORCNT) : 0U, initialized ? CanRead(CAN_RXERRORCNT) : 0U,
               initialized ? CanRead(CAN_STATE) : 0U, ret);
    return ret;
}
