/* Temporary J4 physical UART4 <-> UART3 test. No Linux/RPMsg serial proxy.
 * Only this instance's CRU/IOC fields and SPI bytes are modified.
 * RBR/THR data transfers are exclusively in the interrupt handler.
 */
#include "prt_config.h"
#include "prt_hwi.h"
#include "prt_task.h"
#include "prt_typedef.h"
#include "cpu_config.h"
#include "test.h"
#include "rk3572_rs232_codec.h"

#define PCLK_GATE 0x26090838ULL
#define PCLK_RESET 0x26090A38ULL
#if (MCS_CLIENT_CPU_ID == 4)
#define UART_BASE 0x2C160000ULL
#define UART_INTID 160U
#define UART_NUMBER 4U
#define PCLK_MASK 0x0080U
#define SCLK_GATE 0x2609083CULL
#define SCLK_RESET 0x26090A3CULL
#define SCLK_MASK 0x0040U
#define CLOCK_SELECT 0x26090428ULL
#define IOC_MUX 0x2607400CULL
#define IOC_MASK 0x00FFU
#define IOC_VALUE 0x0099U
#define EXPECTED_MPIDR 0x100U
#elif (MCS_CLIENT_CPU_ID == 5)
#define UART_BASE 0x2C1A0000ULL
#define UART_INTID 164U
#define UART_NUMBER 8U
#define PCLK_MASK 0x0800U
#define SCLK_GATE 0x26090840ULL
#define SCLK_RESET 0x26090A40ULL
#define SCLK_MASK 0x0004U
#define CLOCK_SELECT 0x26090438ULL
#define IOC_MUX 0x26074010ULL
#define IOC_MASK 0x0FF0U
#define IOC_VALUE 0x0990U
#define EXPECTED_MPIDR 0x101U
#else
#error "RS232 test supports CPU4/CPU5 only"
#endif
#if (M7_RS232_BAUD == 115200)
#define UART_DIVISOR 13U
#elif (M7_RS232_BAUD == 38400)
#define UART_DIVISOR 39U
#elif (M7_RS232_BAUD == 9600)
#define UART_DIVISOR 156U
#else
#error "RS232 test baud must be 9600, 38400 or 115200"
#endif
#define FRAMES 1000U
#define WAIT_TICKS 3000U
#define RX_RING_SIZE 128U
#define RBR_THR_DLL 0U
#define IER_DLH 1U
#define IIR_FCR 2U
#define LCR 3U
#define MCR 4U
#define LSR 5U
#define USR 31U
#define IER_RX_LINE 5U
#define IER_TX 2U
#define LSR_ERRORS 0x1EU
struct UartState {
    volatile U32 irq, txIrq, rxIrq, txBytes, rxBytes, errors, overflow, wrongCpu, busy, storm;
    volatile U32 txPos, txLength, rxRead, rxWrite;
    U8 tx[RS232_FRAME_SIZE], rx[RX_RING_SIZE];
    U32 txFrames, rxFrames;
    U8 target, savedTarget, savedPriority;
};
static struct UartState g_uart;
static U32 Read32(U64 addr) { return *(volatile U32 *)(uintptr_t)addr; }
static void Write32(U64 addr, U32 value)
{
    *(volatile U32 *)(uintptr_t)addr = value;
    __asm__ volatile("dsb sy" ::: "memory");
}
static void WriteByte(U64 addr, U8 value)
{
    *(volatile U8 *)(uintptr_t)addr = value;
    __asm__ volatile("dsb sy" ::: "memory");
}
static U32 UartRead(U32 reg) { return Read32(UART_BASE + reg * 4U); }
static void UartWrite(U32 reg, U32 value) { Write32(UART_BASE + reg * 4U, value); }
static void Hiword(U64 addr, U32 mask, U32 value) { Write32(addr, (mask << 16) | (value & mask)); }
static U32 Affinity(void)
{
    U64 value;
    __asm__ volatile("mrs %0, mpidr_el1" : "=r"(value));
    return (U32)value & 0xFFFFFFU;
}
static void SpiWrite(U32 offset)
{
    Write32(GIC_DIST_BASE + offset + (UART_INTID / 32U) * 4U, 1U << (UART_INTID % 32U));
}
static U32 BadState(void)
{
    return g_uart.errors || g_uart.overflow || g_uart.wrongCpu || g_uart.storm;
}
static U32 InitializeResources(void)
{
    PRT_Printf("[rs232] UP%u before pgate=0x%x sgate=0x%x preset=0x%x sreset=0x%x select=0x%x\n",
        MCS_CLIENT_CPU_ID - 3U, Read32(PCLK_GATE), Read32(SCLK_GATE),
        Read32(PCLK_RESET), Read32(SCLK_RESET), Read32(CLOCK_SELECT));
    SpiWrite(0x180U);
    Hiword(PCLK_GATE, PCLK_MASK, 0U); Hiword(SCLK_GATE, SCLK_MASK, 0U);
    Hiword(PCLK_RESET, PCLK_MASK, PCLK_MASK); Hiword(SCLK_RESET, SCLK_MASK, SCLK_MASK);
    (void)PRT_TaskDelay(1U);
    /* Own UART source selects xin24m (selector 3), divider 1. No shared PLL/frac writes. */
    Hiword(CLOCK_SELECT, 0x07FFU, 0x0300U);
    Hiword(IOC_MUX, IOC_MASK, IOC_VALUE);
    Hiword(PCLK_RESET, PCLK_MASK, 0U); Hiword(SCLK_RESET, SCLK_MASK, 0U);
    (void)PRT_TaskDelay(1U);
    if ((Read32(PCLK_GATE) & PCLK_MASK) || (Read32(SCLK_GATE) & SCLK_MASK) ||
        (Read32(PCLK_RESET) & PCLK_MASK) || (Read32(SCLK_RESET) & SCLK_MASK) ||
        ((Read32(CLOCK_SELECT) & 0x07FFU) != 0x0300U) ||
        ((Read32(IOC_MUX) & IOC_MASK) != IOC_VALUE)) { return 10U; }
    return 0U;
}
static void UartIsr(uintptr_t argument)
{
    U32 loop, cause, status, count;
    (void)argument;
    g_uart.irq++;
    if (Affinity() != EXPECTED_MPIDR) { g_uart.wrongCpu++; }
    for (loop = 0; loop < 128U; loop++) {
        cause = UartRead(IIR_FCR) & 15U;
        if (cause & 1U) {
            if (cause == 7U) { (void)UartRead(USR); g_uart.busy++; continue; }
            return;
        }
        if (cause == 2U) {
            g_uart.txIrq++;
            /* One byte per THRE IRQ: no assumption about FIFO depth. */
            if (g_uart.txPos < g_uart.txLength) {
                UartWrite(RBR_THR_DLL, g_uart.tx[g_uart.txPos]);
                g_uart.txPos++; g_uart.txBytes++;
            } else { UartWrite(IER_DLH, IER_RX_LINE); }
        } else if (cause == 4U || cause == 6U || cause == 12U) {
            g_uart.rxIrq++;
            for (count = 0; count < 128U; count++) {
                U8 value;
                status = UartRead(LSR); g_uart.errors |= status & LSR_ERRORS;
                if (!(status & 1U)) { break; }
                value = (U8)UartRead(RBR_THR_DLL); g_uart.rxBytes++;
                if (g_uart.rxWrite - g_uart.rxRead >= RX_RING_SIZE) { g_uart.overflow++; }
                else { g_uart.rx[g_uart.rxWrite % RX_RING_SIZE] = value; g_uart.rxWrite++; }
            }
        } else { g_uart.storm++; UartWrite(IER_DLH, 0U); return; }
    }
    g_uart.storm++; UartWrite(IER_DLH, 0U);
}
static U32 InitializeController(void)
{
    U32 ret;
    U64 priority = GIC_DIST_BASE + 0x400U + UART_INTID;
    U64 target = GIC_DIST_BASE + 0x800U + UART_INTID;
    g_uart.savedPriority = *(volatile U8 *)(uintptr_t)priority;
    g_uart.savedTarget = *(volatile U8 *)(uintptr_t)target;
    g_uart.target = *(volatile U8 *)(uintptr_t)(GIC_DIST_BASE + 0x800U);
    if (Affinity() != EXPECTED_MPIDR || !g_uart.target || (g_uart.target & (g_uart.target - 1U))) {
        return 11U;
    }
    UartWrite(IER_DLH, 0U); UartWrite(MCR, 0U); UartWrite(IIR_FCR, 7U);
    UartWrite(LCR, 0x80U); UartWrite(RBR_THR_DLL, UART_DIVISOR); UartWrite(IER_DLH, 0U);
    UartWrite(LCR, 3U); UartWrite(IIR_FCR, 7U);  /* FIFO enabled, 8N1, trigger 1 byte. */
    if (UartRead(LCR) != 3U) { return 12U; }
    ret = PRT_HwiSetAttr(UART_INTID, 10U, OS_HWI_MODE_ENGROSS);
    if (ret) { return ret; }
    ret = PRT_HwiCreate(UART_INTID, UartIsr, 0U);
    if (ret) { return ret; }
    WriteByte(priority, 0xA0U); WriteByte(target, g_uart.target);
    SpiWrite(0x280U); SpiWrite(0x100U); UartWrite(IER_DLH, IER_RX_LINE);
    PRT_Printf("[rs232] UP%u ready uart=%u mpidr=0x%x intid=%u target=0x%x baud=%u clock=24000000 divisor=%u lcr=0x%x\n",
        MCS_CLIENT_CPU_ID - 3U, UART_NUMBER, Affinity(), UART_INTID, g_uart.target,
        M7_RS232_BAUD, UART_DIVISOR, UartRead(LCR));
    return 0U;
}
static U32 Transmit(const U8 *frame)
{
    U32 i, ticks, status;
    uintptr_t lock = PRT_HwiLock();
    for (i = 0; i < RS232_FRAME_SIZE; i++) { g_uart.tx[i] = frame[i]; }
    g_uart.txPos = 0U; g_uart.txLength = RS232_FRAME_SIZE;
    UartWrite(IER_DLH, IER_RX_LINE | IER_TX); PRT_HwiRestore(lock);
    for (ticks = 0; ticks < WAIT_TICKS; ticks++) {
        uintptr_t statusLock;
        if (BadState()) { return 20U; }
        /* TEMT confirms the last stop bit left the wire; only data writes use the ISR. */
        statusLock = PRT_HwiLock();
        status = UartRead(LSR); g_uart.errors |= status & LSR_ERRORS;
        PRT_HwiRestore(statusLock);
        if (g_uart.errors) { return 20U; }
        if (g_uart.txPos == RS232_FRAME_SIZE && (status & 0x40U)) {
            g_uart.txFrames++; return 0U;
        }
        (void)PRT_TaskDelay(1U);
    }
    return 21U;
}
static U32 Receive(U8 *frame, U32 timeout)
{
    U32 ticks, i;
    for (ticks = 0; ticks < timeout; ticks++) {
        if (BadState()) { return 22U; }
        if (g_uart.rxWrite - g_uart.rxRead >= RS232_FRAME_SIZE) {
            uintptr_t lock = PRT_HwiLock();
            for (i = 0; i < RS232_FRAME_SIZE; i++) {
                frame[i] = g_uart.rx[g_uart.rxRead % RX_RING_SIZE]; g_uart.rxRead++;
            }
            PRT_HwiRestore(lock); g_uart.rxFrames++; return 0U;
        }
        (void)PRT_TaskDelay(1U);
    }
    return 23U;
}
static U32 RunPair(void)
{
    U8 request[RS232_FRAME_SIZE], response[RS232_FRAME_SIZE];
    U32 sequence, ret;
#if (MCS_CLIENT_CPU_ID == 4)
    (void)PRT_TaskDelay(1000U);
#endif
    for (sequence = 0; sequence < FRAMES; sequence++) {
#if (MCS_CLIENT_CPU_ID == 4)
        Rs232Fill(request, 'A', sequence); ret = Transmit(request);
        if (!ret) { ret = Receive(response, WAIT_TICKS); }
        if (!ret && !Rs232Matches(response, 'B', sequence)) { ret = 24U; }
#else
        ret = Receive(request, sequence ? WAIT_TICKS : 30000U);
        if (!ret && !Rs232Matches(request, 'A', sequence)) { ret = 25U; }
        if (!ret) { Rs232Fill(response, 'B', sequence); ret = Transmit(response); }
#endif
        if (ret) {
            PRT_Printf("[rs232] UP%u fail seq=%u rc=%u lsr=0x%x iir=0x%x usr=0x%x\n",
                MCS_CLIENT_CPU_ID - 3U, sequence, ret, UartRead(LSR), UartRead(IIR_FCR), UartRead(USR));
            return ret;
        }
    }
    return 0U;
}
U32 Rk3572Rs232Test(void)
{
    U32 ret = InitializeResources(), initialized = 0U;
    if (!ret) {
        initialized = 1U; ret = InitializeController();
        if (!ret) { ret = RunPair(); }
        UartWrite(IER_DLH, 0U); UartWrite(IIR_FCR, 7U);
    }
    SpiWrite(0x180U); SpiWrite(0x280U);
    if (initialized) {
        WriteByte(GIC_DIST_BASE + 0x800U + UART_INTID, g_uart.savedTarget);
        WriteByte(GIC_DIST_BASE + 0x400U + UART_INTID, g_uart.savedPriority);
    }
    if (!ret && (BadState() || g_uart.txBytes != FRAMES * RS232_FRAME_SIZE ||
        g_uart.rxBytes != FRAMES * RS232_FRAME_SIZE || g_uart.rxWrite != g_uart.rxRead ||
        !g_uart.txIrq || !g_uart.rxIrq)) { ret = 26U; }
    PRT_Printf("[rs232] UP%u counts irq=%u txirq=%u rxirq=%u txbytes=%u rxbytes=%u err=0x%x overflow=%u wrongcpu=%u busy=%u storm=%u target=0x%x\n",
        MCS_CLIENT_CPU_ID - 3U, g_uart.irq, g_uart.txIrq, g_uart.rxIrq, g_uart.txBytes,
        g_uart.rxBytes, g_uart.errors, g_uart.overflow, g_uart.wrongCpu, g_uart.busy, g_uart.storm, g_uart.target);
    PRT_Printf("[rs232] UP%u direct %s baud=%u tx=%u rx=%u bytes=%u rc=%u\n",
        MCS_CLIENT_CPU_ID - 3U, ret ? "FAIL" : "PASS", M7_RS232_BAUD,
        g_uart.txFrames, g_uart.rxFrames, RS232_FRAME_SIZE, ret);
    return ret;
}
