/* UP2 owns GMAC1 clocks/mux/MDIO/PHY/MAC/DMA after explicit host handoff.
 * Linux holds only the shared NVM0 power domain; ETH3 is the physical test peer.
 * First slice uses bounded DMA polling, all Ethernet interrupts masked.
 */
#include "prt_config.h"
#include "prt_task.h"
#include "cpu_config.h"
#include "test.h"
#include "rk3572_integrated.h"
#include "rk3572_eth_codec.h"
#ifdef M7_POWERLINK_EDRV
#include "m7_eth2_hw.h"
#endif

#if (MCS_CLIENT_CPU_ID == 5)
#define MAC 0x2a040000UL
#define DMA_AREA 0x7ca10000UL
#define RING 8U
#define OWN (1U << 31)
struct EthDesc { volatile U32 d[4]; };
struct EthDma { struct EthDesc tx[RING], rx[RING]; U8 txbuf[2048]; U8 rxbuf[RING][2048]; };
_Static_assert(sizeof(struct EthDma) <= 0x10000U, "DMA exceeds own reserved noncached window");
static struct EthDma *const g_dma = (struct EthDma *)DMA_AREA;
static const U8 g_mac[6] = {0x02, 0x55, 0x50, 0x32, 0x00, 0x02};
#ifdef M7_POWERLINK_EDRV
/* 0 free, 1 legacy test, 2 POWERLINK. A failed reset retains the lease. */
static U32 g_ethLease;
static int TakeLease(U32 owner)
{ U32 expected = 0U; return __atomic_compare_exchange_n(&g_ethLease, &expected, owner, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE); }
#endif
static U32 Read(uintptr_t a) { return *(volatile U32 *)a; }
static void Write(uintptr_t a, U32 v) { *(volatile U32 *)a = v; __asm__ volatile("dsb sy" ::: "memory"); }
static U32 Reg(U32 offset) { return Read(MAC + offset); }
static void Set(U32 offset, U32 value) { Write(MAC + offset, value); }
static void Field(uintptr_t address, U32 mask, U32 value) { Write(address, (mask << 16) | (value & mask)); }
static U64 Counter(void) { U64 v; __asm__ volatile("mrs %0, cntpct_el0" : "=r"(v)); return v; }
static U64 Seconds(U32 n) { U64 v; __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(v)); return v * n; }
static int Wait(U32 offset, U32 mask, U32 value)
{
    U64 limit = Counter() + Seconds(1U);
    do { if ((Reg(offset) & mask) == value) { return 1; } (void)PRT_TaskDelay(1U); } while (Counter() < limit);
    return 0;
}
static int Mdio(U32 reg, U32 *value, int write)
{
    /* CSR/pclk = 100MHz: divider 62 (CR=0), MDC below 2.5MHz. */
    if (!Wait(0x200U, 1U, 0U)) { return 0; }
    Set(0x204U, write ? *value : 0U);
    Set(0x200U, (1U << 21) | (reg << 16) | (write ? 4U : 12U) | 1U);
    if (!Wait(0x200U, 1U, 0U)) { return 0; }
    if (!write) { *value = Reg(0x204U) & 0xffffU; }
    return 1;
}
static int PhyWrite(U32 reg, U32 value) { return Mdio(reg, &value, 1); }
static int PageWrite(U32 page, U32 reg, U32 value)
{ return PhyWrite(31U, page) && PhyWrite(reg, value) && PhyWrite(31U, 0U); }
static void OwnResources(void)
{
    /* Never change CPLL/GPLL/shared bus roots or GMAC0/ETH1 fields. */
    Field(0x26090388UL, 0x001fU, 7U);           /* own CPLL / 8, 125 MHz */
    Field(0x260903a8UL, 0xff00U, 0xa700U);     /* own CPLL / 40, PHY 25 MHz */
    Field(0x2609080cUL, 0x0100U, 0U);
    Field(0x26090814UL, 0x0080U, 0U);
    Field(0x260908a8UL, 0xc000U, 0U);
    /* GPIO1 M1: B4..B7,C0,C1,C4..C7,D0..D3. D4 refclock retained from DT. */
    Field(0x2608202cUL, 0xffffU, 0x1111U);
    Field(0x26082030UL, 0x00ffU, 0x0011U);
    Field(0x26082034UL, 0xffffU, 0x1111U);
    Field(0x26082038UL, 0xffffU, 0x1111U);
    PRT_Printf("[eth] own clocks/mux ready; entering NVM0 GRF\n");
    Field(0x2602a020UL, 0x0ef8U, 0x0260U); /* RGMII, CRU, 100 Mbps */
    Field(0x26082608UL, 0xffffU, 0x00a0U); /* TX delay 0x20 enabled, RX delay off */
    PRT_Printf("[eth] RGMII/delay configured; resetting own MAC\n");
    Field(0x26090aa8UL, 0x4000U, 0x4000U);
    (void)PRT_TaskDelay(1U);
    Field(0x26090aa8UL, 0x4000U, 0U);
}
static int PhyInit(int halfDuplex)
{
    static const U32 settings[][3] = {
        {0xdab,0x17,0xf13}, {0xd8f,0x10,0x300}, {0xd96,0x15,0xc08a},
        {0xda4,0x12,0x7bc}, {0xd8f,0x16,0x2500}, {0xd90,0x16,0x1555},
        {0xd92,0x11,0x2b15}, {0xd96,0x16,0x4010}, {0xda5,0x11,0x4a12},
        {0xda5,0x12,0x4a12}, {0xda8,0x11,0x175}, {0xd99,0x16,0xa},
        {0xd95,0x13,0x5b00}, {0xa43,0x19,0x823}, {0xd04,0x10,0xae00}
    };
    U32 high, low, value, i;
    U64 limit;
    if (!PhyWrite(31U, 0U) || !Mdio(2U, &high, 0) || !Mdio(3U, &low, 0)) { return 0; }
    PRT_Printf("[eth] PHY id=0x%x%x MAC version=0x%x\n", high, low, Reg(0x110U));
    if (high != 0x7b74U || low != 0x4412U) { return 0; }
    /* Exact MAE0621A/B-Q3C(I) config/resume sequence from vendor Linux maxio.c. */
    for (i = 0U; i < sizeof(settings) / sizeof(settings[0]); i++) {
        if (!PageWrite(settings[i][0], settings[i][1], settings[i][2])) { return 0; }
    }
    if (!PhyWrite(0U, 0x9140U)) { return 0; }
    limit = Counter() + Seconds(2U);
    do {
        if (!Mdio(0U, &value, 0)) { return 0; }
        if (!(value & 0x8000U)) { break; }
        (void)PRT_TaskDelay(1U);
    } while (Counter() < limit);
    if (value & 0x8000U) { return 0; }
    if (!PageWrite(0xdaaU, 0x17U, 0x1001U) || !PageWrite(0xdabU, 0x15U, 0U) ||
        !PhyWrite(9U, 0U) || !PhyWrite(4U, halfDuplex ? 0x0081U : 0x0101U) ||
        !PhyWrite(0U, halfDuplex ? 0x2000U : 0x1200U)) { return 0; }
    if (halfDuplex) {
        /* Forced 100-half, AN disabled. The isolated peer must match this mode. */
        if (!Mdio(0U, &value, 0) || (value & 0xffc0U) != 0x2000U ||
            !Mdio(1U, &value, 0) || !(value & 0x2000U)) { return 0; }
    }
    limit = Counter() + Seconds(12U);
    do {
        if (!Mdio(1U, &value, 0) || !Mdio(1U, &value, 0)) { return 0; }
        if (halfDuplex && (value & 0x4U)) {
            PRT_Printf("[eth] PHY forced 100-half link ready; AN disabled, bmsr=0x%x\n", value);
            return 1;
        }
        if (!halfDuplex && (value & 0x24U) == 0x24U) {
            U32 partner;
            if (!Mdio(5U, &partner, 0) || !(partner & 0x0100U)) { return 0; }
            PRT_Printf("[eth] MDIO/PHY PASS link=100-full bmsr=0x%x partner=0x%x\n", value, partner);
            return 1;
        }
        (void)PRT_TaskDelay(10U);
    } while (Counter() < limit);
    PRT_Printf("[eth] link timeout bmsr=0x%x\n", value);
    return 0;
}
static int ResetDma(void)
{ Set(0x1134U, 0U); Set(0xb4U, 0U); Set(0x1000U, 1U); return Wait(0x1000U, 1U, 0U); }
static int DmaInit(void)
{
    U32 i, feature = Reg(0x120U), tx = (128U << ((feature >> 6) & 31U)), rx = (128U << (feature & 31U));
    if (tx < 2048U || rx < 2048U || tx > 131072U || rx > 262144U || !ResetDma()) { return 0; }
    memset(g_dma, 0, sizeof(*g_dma));
    for (i = 0U; i < RING; i++) {
        g_dma->rx[i].d[0] = (U32)(uintptr_t)g_dma->rxbuf[i];
        g_dma->rx[i].d[3] = OWN | (1U << 24);
    }
    __asm__ volatile("dsb sy" ::: "memory");
    Set(0x300U, 0x80000200U); Set(0x304U, 0x32505502U);
    Set(8U, 0U); Set(0xa0U, 2U); Set(0xc30U, 0U);
    Set(0xd00U, ((tx / 256U - 1U) << 16) | 10U);
    Set(0xd30U, ((rx / 256U - 1U) << 20) | 32U);
    Set(0x1004U, 0x100eU); Set(0x1100U, 0U);
    Set(0x1110U, 0U); Set(0x1114U, (U32)(uintptr_t)g_dma->tx);
    Set(0x1118U, 0U); Set(0x111cU, (U32)(uintptr_t)g_dma->rx);
    Set(0x112cU, RING - 1U); Set(0x1130U, RING - 1U);
    Set(0x1120U, (U32)(uintptr_t)g_dma->tx);
    Set(0x1128U, (U32)(uintptr_t)(g_dma->rx + RING));
    Set(0x1104U, (8U << 16) | 1U);
    Set(0x1108U, (8U << 16) | (2048U << 1) | 1U);
    /* Automatic FCS/pad stripping; no loopback, checksum offload or interrupts. */
    Set(0U, (1U << 20) | (1U << 15) | (1U << 14) | (1U << 13) | 3U);
    return 1;
}
static U32 Frames(U32 length)
{
    U32 next = 0U, received = 0U, sent = 0U, ignored = 0U, result = 0U;
    U64 limit = Counter() + Seconds(35U);
    PRT_Printf("[eth] READY raw=%u count=1000 mac=02:55:50:32:00:02 DMA=0x7ca10000 polling\n", length);
    while (received < 1000U && Counter() < limit) {
        struct EthDesc *desc = &g_dma->rx[next];
        U32 status = desc->d[3], size;
        U8 *packet = g_dma->rxbuf[next];
        if (status & OWN) { (void)PRT_TaskDelay(1U); continue; }
        __asm__ volatile("dmb sy" ::: "memory");
        size = status & 0x7fffU;
        if ((status & (1U << 15)) || (status & 0x30000000U) != 0x30000000U || size > 2048U) { result = 4U; break; }
        if (size < 38U || memcmp(packet, g_mac, 6) || packet[12] != 0x88U || packet[13] != 0xb5U) { ignored++; }
        else {
            U32 slot = sent % RING;
            struct EthDesc *td = &g_dma->tx[slot];
            /* Some MAC revisions retain FCS in descriptor length even with ACS. */
            if ((size != length && size != length + 4U) || !EthValidate(packet, length, received, 1U)) { result = 5U; break; }
            memcpy(g_dma->txbuf, packet, length);
            memcpy(g_dma->txbuf, packet + 6, 6); memcpy(g_dma->txbuf + 6, g_mac, 6);
            EthPut32(g_dma->txbuf + 22, 2U);
            EthPut32(g_dma->txbuf + length - 4U, EthCrc(g_dma->txbuf + 14, length - 18U));
            td->d[0] = (U32)(uintptr_t)g_dma->txbuf; td->d[1] = 0U; td->d[2] = length;
            __asm__ volatile("dmb sy" ::: "memory");
            td->d[3] = OWN | 0x30000000U | length;
            __asm__ volatile("dsb sy" ::: "memory");
            Set(0x1120U, (U32)(uintptr_t)&g_dma->tx[(slot + 1U) % RING]);
            {
                U64 txlimit = Counter() + Seconds(1U);
                while ((td->d[3] & OWN) && Counter() < txlimit) { (void)PRT_TaskDelay(1U); }
            }
            if ((td->d[3] & (OWN | (1U << 15))) || (Reg(0x1160U) & (1U << 12))) { result = 6U; break; }
            sent++; received++;
        }
        desc->d[0] = (U32)(uintptr_t)packet; desc->d[1] = 0U; desc->d[2] = 0U;
        __asm__ volatile("dmb sy" ::: "memory");
        desc->d[3] = OWN | (1U << 24);
        __asm__ volatile("dsb sy" ::: "memory");
        Set(0x1128U, (U32)(uintptr_t)desc);
        next = (next + 1U) % RING;
    }
    if (!result && received != 1000U) { result = 7U; }
    PRT_Printf("[eth] %s raw=%u rx=%u tx=%u rxbytes=%u txbytes=%u ignored=%u status=0x%x rc=%u\n",
        result ? "FAIL" : "PASS", length, received, sent, received * length, sent * length, ignored, Reg(0x1160U), result);
    if (result) { PRT_Printf("[eth] DEBUG rxdesc=0x%x rxcur=0x%x txcur=0x%x mtlrx=0x%x\n", g_dma->rx[next].d[3], Reg(0x114cU), Reg(0x1144U), Reg(0xd38U)); }
    return result;
}
U32 Rk3572EthTest(U32 length)
{
    U32 result = 0U;
    if (length != 0U && length != 64U && length != 1514U) { return 1U; }
#ifdef M7_POWERLINK_EDRV
    if (!TakeLease(1U)) { return 10U; }
#endif
    /* A held power domain does not imply its shared bus roots are ungated.
     * Refuse BEFORE any GRF/MAC transaction; do not reset an inaccessible MAC.
     * Linux/platform owns these roots; UP2 must never rewrite their gate/rate.
     */
    {
        U32 gate = Read(0x260908a8UL);
        PRT_Printf("[eth] begin profile=%u CRU42=0x%x\n", length, gate);
        if (gate & 0x6U) {
#ifdef M7_POWERLINK_EDRV
            __atomic_store_n(&g_ethLease, 0U, __ATOMIC_RELEASE);
#endif
            PRT_Printf("[eth] SAFE-NO-START shared fabric root gated; rc=9\n");
            return 9U;
        }
    }
    OwnResources();
    PRT_Printf("[eth] own clock/reset/mux complete; entering MDIO\n");
    if (!PhyInit(0)) { result = 2U; }
    else if (length) {
        if (!DmaInit()) { result = 3U; }
        else { result = Frames(length); }
    }
    Set(0x1134U, 0U); Set(0xb4U, 0U);
    Set(0U, Reg(0U) & ~3U); Set(0x1104U, Reg(0x1104U) & ~1U); Set(0x1108U, Reg(0x1108U) & ~1U);
    if (!ResetDma()) { result = 8U; PRT_Printf("[eth] UNSAFE DMA reset timeout: retain host power hold\n"); }
    else {
#ifdef M7_POWERLINK_EDRV
        __atomic_store_n(&g_ethLease, 0U, __ATOMIC_RELEASE);
#endif
        PRT_Printf("[eth] QUIESCED reset=1 MAC=0x%x txctl=0x%x rxctl=0x%x\n", Reg(0U), Reg(0x1104U), Reg(0x1108U));
    }
    return result;
}
#ifdef M7_POWERLINK_EDRV
uint32_t m7_eth2_hw_read(uint32_t offset) { return Reg(offset); }
void m7_eth2_hw_write(uint32_t offset, uint32_t value) { Set(offset, value); }
int m7_eth2_hw_stop(void)
{
    if (__atomic_load_n(&g_ethLease, __ATOMIC_ACQUIRE) != 2U || (Read(0x260908a8UL) & 0x6U)) { return 0; }
    Set(0x1134U, 0U); Set(0xb4U, 0U);
    Set(0U, Reg(0U) & ~3U); Set(0x1104U, Reg(0x1104U) & ~1U); Set(0x1108U, Reg(0x1108U) & ~1U);
    if (!ResetDma()) {
        PRT_Printf("[plk-edrv] UNSAFE reset timeout; retain power/root hold and lease\n");
        return 0;
    }
    __atomic_store_n(&g_ethLease, 0U, __ATOMIC_RELEASE);
    PRT_Printf("[plk-edrv] QUIESCED reset=1; aborted TX is not completion\n");
    return 1;
}
int m7_eth2_hw_acquire(void)
{
    U32 feature, tx, rx;
    if (!TakeLease(2U)) { return 0; }
    if (Read(0x260908a8UL) & 0x6U) {
        __atomic_store_n(&g_ethLease, 0U, __ATOMIC_RELEASE);
        return 0; /* No GRF/MAC access when shared fabric is gated. */
    }
    OwnResources();
    feature = Reg(0x120U);
    tx = 128U << ((feature >> 6) & 31U); rx = 128U << (feature & 31U);
    if (Reg(0x110U) != 0x5051U || !(Reg(0x11cU) & (1U << 2)) ||
        tx < 2048U || tx > 131072U || rx < 2048U || rx > 262144U ||
        !PhyInit(1) || !ResetDma()) {
        return m7_eth2_hw_stop() ? 0 : -1;
    }
    return 1;
}
int m7_eth2_hw_start(struct M7Eth2Dma *dma, const uint8_t mac[6])
{
    U32 feature = Reg(0x120U), tx = 128U << ((feature >> 6) & 31U), rx = 128U << (feature & 31U);
    Set(0x300U, 0x80000000U | ((U32)mac[5] << 8) | mac[4]);
    Set(0x304U, ((U32)mac[3] << 24) | ((U32)mac[2] << 16) | ((U32)mac[1] << 8) | mac[0]);
    /* Receive multicast in hardware, exact DA + 22-byte filters in EDRV software.
     * No promiscuous unicast, VLAN, flow control, checksum, timestamp or IRQ. */
    Set(8U, 1U << 4); Set(4U, 0U); Set(0xa0U, 2U); Set(0xc30U, 0U);
    Set(0x70U, 0U); Set(0x90U, 0U);
    Set(0xd00U, ((tx / 256U - 1U) << 16) | 10U); Set(0xd30U, ((rx / 256U - 1U) << 20) | 32U);
    Set(0x1004U, 0x100eU); Set(0x1100U, 0U);
    Set(0x1110U, 0U); Set(0x1114U, (U32)(uintptr_t)dma->tx);
    Set(0x1118U, 0U); Set(0x111cU, (U32)(uintptr_t)dma->rx);
    Set(0x112cU, M7_ETH2_RING - 1U); Set(0x1130U, M7_ETH2_RING - 1U);
    Set(0x1120U, (U32)(uintptr_t)dma->tx); Set(0x1128U, (U32)(uintptr_t)(dma->rx + M7_ETH2_RING));
    Set(0x1104U, (8U << 16) | 1U); Set(0x1108U, (8U << 16) | (M7_ETH2_BUFFER_SIZE << 1) | 1U);
    /* PS/FES=100M, DM=0 half-duplex, ACS/CST=0: EDRV strips exactly 4B FCS. */
    Set(0U, (1U << 15) | (1U << 14) | 3U);
    if ((Reg(0U) & 0x0030e003U) != 0x0000c003U) { return 0; }
    PRT_Printf("[plk-edrv] started 100-half polling, DMA=%p bytes=%u; not MN runtime\n", dma, (U32)sizeof(*dma));
    return 1;
}
#endif
#else
U32 Rk3572EthTest(U32 length) { (void)length; return 1U; }
#endif
