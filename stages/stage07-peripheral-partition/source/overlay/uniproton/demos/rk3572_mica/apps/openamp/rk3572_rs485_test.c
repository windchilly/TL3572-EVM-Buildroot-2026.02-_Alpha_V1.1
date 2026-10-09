/* Temporary half-duplex RS485 SoC UART1/CPU4 <-> UART2/CPU5 test.
 * RE/DE are tied to RTSN: physical high=TX, low=RX.
 * Use manual MCR.RTS, not auto RTS/CTS or Linux GPIO forwarding.
 * UART data transfers remain exclusively in the interrupt handler.
 */
#include "prt_config.h"
#include "prt_hwi.h"
#include "prt_task.h"
#include "prt_typedef.h"
#include "cpu_config.h"
#include "test.h"
#include "rk3572_rs232_codec.h"

#if (MCS_CLIENT_CPU_ID == 4)
#define UART_BASE 0x26500000ULL
#define UART_INTID 157U
#define UART_NUMBER 1U
#define PCLK_GATE 0x260B0814ULL
#define PCLK_RESET 0x260B0A14ULL
#define PCLK_MASK 0x0080U
#define SCLK_GATE 0x260B0814ULL
#define SCLK_RESET 0x260B0A14ULL
#define SCLK_MASK 0x0040U
#define CLOCK_SELECT 0x260B0320ULL
#define SELECT_MASK 0x0003U
#define SELECT_VALUE 0x0001U
#define IOC_TX 0x26074010ULL
#define IOC_TX_MASK 0x000FU
#define IOC_TX_VALUE 0x0009U
#define IOC_RX 0x2607400CULL
#define IOC_RX_MASK 0xF000U
#define IOC_RX_VALUE 0x9000U
#define IOC_RTS 0x26074018ULL
#define IOC_RTS_MASK 0xF000U
#define IOC_RTS_VALUE 0x9000U
#define EXPECTED_MPIDR 0x100U
#elif (MCS_CLIENT_CPU_ID == 5)
#define UART_BASE 0x2C140000ULL
#define UART_INTID 158U
#define UART_NUMBER 2U
#define PCLK_GATE 0x26090838ULL
#define PCLK_RESET 0x26090A38ULL
#define PCLK_MASK 0x0020U
#define SCLK_GATE 0x2609083CULL
#define SCLK_RESET 0x26090A3CULL
#define SCLK_MASK 0x0001U
#define CLOCK_SELECT 0x26090420ULL
#define SELECT_MASK 0x07FFU
#define SELECT_VALUE 0x0300U
#define IOC_TX 0x2608404CULL
#define IOC_TX_MASK 0x000FU
#define IOC_TX_VALUE 0x0009U
#define IOC_RX 0x2608404CULL
#define IOC_RX_MASK 0x00F0U
#define IOC_RX_VALUE 0x0090U
#define IOC_RTS 0x2608404CULL
#define IOC_RTS_MASK 0x0F00U
#define IOC_RTS_VALUE 0x0C00U
#define EXPECTED_MPIDR 0x101U
#else
#error "RS485 test supports CPU4/CPU5 only"
#endif
#if (M7_RS485_BAUD == 115200)
#define UART_DIVISOR 13U
#elif (M7_RS485_BAUD == 38400)
#define UART_DIVISOR 39U
#elif (M7_RS485_BAUD == 9600)
#define UART_DIVISOR 156U
#else
#error "RS485 test baud must be 9600, 38400 or 115200"
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
    volatile U32 txPos, txLength, rxRead, rxWrite, txTurns, rxTurns, dirErrors;
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
    return g_uart.errors || g_uart.overflow || g_uart.wrongCpu || g_uart.storm || g_uart.dirErrors;
}
static U32 SetDirection(U32 transmit)
{
    U32 value = transmit ? 0U : 2U; /* MCR.RTS is the complement of physical RTSN. */
    UartWrite(MCR, value);
    if (UartRead(MCR) != value) { g_uart.dirErrors++; return 13U; }
    if (transmit) { g_uart.txTurns++; } else { g_uart.rxTurns++; }
    return 0U;
}
static U32 InitializeResources(void)
{
    PRT_Printf("[rs485] UP%u before pgate=0x%x sgate=0x%x preset=0x%x sreset=0x%x select=0x%x\n",
        MCS_CLIENT_CPU_ID - 3U, Read32(PCLK_GATE), Read32(SCLK_GATE),
        Read32(PCLK_RESET), Read32(SCLK_RESET), Read32(CLOCK_SELECT));
    SpiWrite(0x180U);
    Hiword(PCLK_GATE, PCLK_MASK, 0U); Hiword(SCLK_GATE, SCLK_MASK, 0U);
    Hiword(PCLK_RESET, PCLK_MASK, PCLK_MASK); Hiword(SCLK_RESET, SCLK_MASK, SCLK_MASK);
    (void)PRT_TaskDelay(1U);
    /* UART1 selects PMU xin24m directly; UART2 selects main xin24m/div1. */
    Hiword(CLOCK_SELECT, SELECT_MASK, SELECT_VALUE);
    Hiword(IOC_TX, IOC_TX_MASK, IOC_TX_VALUE); Hiword(IOC_RX, IOC_RX_MASK, IOC_RX_VALUE);
    Hiword(PCLK_RESET, PCLK_MASK, 0U); Hiword(SCLK_RESET, SCLK_MASK, 0U);
    (void)PRT_TaskDelay(1U);
    if ((Read32(PCLK_GATE) & PCLK_MASK) || (Read32(SCLK_GATE) & SCLK_MASK) ||
        (Read32(PCLK_RESET) & PCLK_MASK) || (Read32(SCLK_RESET) & SCLK_MASK) ||
        ((Read32(CLOCK_SELECT) & SELECT_MASK) != SELECT_VALUE) ||
        ((Read32(IOC_TX) & IOC_TX_MASK) != IOC_TX_VALUE) ||
        ((Read32(IOC_RX) & IOC_RX_MASK) != IOC_RX_VALUE)) { return 10U; }
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
            } else { UartWrite(IER_DLH, 0U); }
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
    UartWrite(IER_DLH, 0U); UartWrite(MCR, 2U); UartWrite(IIR_FCR, 7U);
    UartWrite(LCR, 0x80U); UartWrite(RBR_THR_DLL, UART_DIVISOR); UartWrite(IER_DLH, 0U);
    UartWrite(LCR, 3U); UartWrite(IIR_FCR, 7U);  /* FIFO enabled, 8N1, trigger 1 byte. */
    if (UartRead(LCR) != 3U) { return 12U; }
    /* Establish receive before connecting RTSN to the transceiver direction input. */
    Hiword(IOC_RTS, IOC_RTS_MASK, IOC_RTS_VALUE);
    if ((Read32(IOC_RTS) & IOC_RTS_MASK) != IOC_RTS_VALUE) { return 14U; }
    ret = SetDirection(0U);
    if (ret) { return ret; }
    ret = PRT_HwiSetAttr(UART_INTID, 10U, OS_HWI_MODE_ENGROSS);
    if (ret) { return ret; }
    ret = PRT_HwiCreate(UART_INTID, UartIsr, 0U);
    if (ret) { return ret; }
    WriteByte(priority, 0xA0U); WriteByte(target, g_uart.target);
    SpiWrite(0x280U); SpiWrite(0x100U); UartWrite(IER_DLH, IER_RX_LINE);
    PRT_Printf("[rs485] UP%u ready uart=%u mpidr=0x%x intid=%u target=0x%x baud=%u clock=24000000 divisor=%u lcr=0x%x\n",
        MCS_CLIENT_CPU_ID - 3U, UART_NUMBER, Affinity(), UART_INTID, g_uart.target,
        M7_RS485_BAUD, UART_DIVISOR, UartRead(LCR));
    return 0U;
}
static U32 Transmit(const U8 *frame)
{
    U32 i, ticks, status, ret;
    uintptr_t lock;
    /* Receiver may finish before the peer's last stop bit/TEMT poll. Guard turnaround. */
    (void)PRT_TaskDelay(4U);
    ret = SetDirection(1U);
    if (ret) { return ret; }
    (void)PRT_TaskDelay(1U); /* More than the transceiver's enable propagation delay. */
    lock = PRT_HwiLock();
    for (i = 0; i < RS232_FRAME_SIZE; i++) { g_uart.tx[i] = frame[i]; }
    g_uart.txPos = 0U; g_uart.txLength = RS232_FRAME_SIZE;
    UartWrite(IER_DLH, IER_TX); PRT_HwiRestore(lock);
    for (ticks = 0; ticks < WAIT_TICKS; ticks++) {
        if (BadState()) { return 20U; }
        lock = PRT_HwiLock();
        status = UartRead(LSR); g_uart.errors |= status & LSR_ERRORS;
        PRT_HwiRestore(lock);
        if (g_uart.errors) { return 20U; }
        if (g_uart.txPos == RS232_FRAME_SIZE && (status & 0x40U)) {
            lock = PRT_HwiLock();
            UartWrite(IER_DLH, 0U); UartWrite(IIR_FCR, 3U);
            ret = SetDirection(0U); UartWrite(IER_DLH, IER_RX_LINE);
            PRT_HwiRestore(lock);
            if (ret) { return ret; }
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
            PRT_Printf("[rs485] UP%u fail seq=%u rc=%u lsr=0x%x iir=0x%x usr=0x%x\n",
                MCS_CLIENT_CPU_ID - 3U, sequence, ret, UartRead(LSR), UartRead(IIR_FCR), UartRead(USR));
            return ret;
        }
    }
    return 0U;
}
U32 Rk3572Rs485Test(void)
{
    U32 ret = InitializeResources(), initialized = 0U;
    if (!ret) {
        initialized = 1U; ret = InitializeController();
        if (!ret) { ret = RunPair(); }
        UartWrite(IER_DLH, 0U); (void)SetDirection(0U); UartWrite(IIR_FCR, 7U);
    }
    SpiWrite(0x180U); SpiWrite(0x280U);
    if (initialized) {
        WriteByte(GIC_DIST_BASE + 0x800U + UART_INTID, g_uart.savedTarget);
        WriteByte(GIC_DIST_BASE + 0x400U + UART_INTID, g_uart.savedPriority);
    }
    if (!ret && (BadState() || g_uart.txBytes != FRAMES * RS232_FRAME_SIZE ||
        g_uart.rxBytes != FRAMES * RS232_FRAME_SIZE || g_uart.rxWrite != g_uart.rxRead ||
        !g_uart.txIrq || !g_uart.rxIrq || g_uart.txTurns != FRAMES ||
        g_uart.rxTurns != FRAMES + 2U || UartRead(MCR) != 2U)) { ret = 26U; }
    PRT_Printf("[rs485] UP%u counts irq=%u txirq=%u rxirq=%u txbytes=%u rxbytes=%u err=0x%x overflow=%u wrongcpu=%u busy=%u storm=%u target=0x%x\n",
        MCS_CLIENT_CPU_ID - 3U, g_uart.irq, g_uart.txIrq, g_uart.rxIrq, g_uart.txBytes,
        g_uart.rxBytes, g_uart.errors, g_uart.overflow, g_uart.wrongCpu, g_uart.busy, g_uart.storm, g_uart.target);
    PRT_Printf("[rs485] UP%u direction tx=%u rx=%u err=%u mcr=0x%x guardticks=4\n",
        MCS_CLIENT_CPU_ID - 3U, g_uart.txTurns, g_uart.rxTurns, g_uart.dirErrors,
        initialized ? UartRead(MCR) : 0U);
    PRT_Printf("[rs485] UP%u direct %s baud=%u tx=%u rx=%u bytes=%u rc=%u\n",
        MCS_CLIENT_CPU_ID - 3U, ret ? "FAIL" : "PASS", M7_RS485_BAUD,
        g_uart.txFrames, g_uart.rxFrames, RS232_FRAME_SIZE, ret);
    return ret;
}
