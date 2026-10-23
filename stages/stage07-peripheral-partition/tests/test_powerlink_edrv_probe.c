/* Real probe + real EDRV + real target; fake RTOS/DMA peer, NOT physical proof. */
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "m7_edrv_probe.h"
#include "m7_edrv_probe_codec.h"
#include "m7_edrv.h"
#include "m7_eth2_hw.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
struct M7Eth2Dma m7_edrv_test_dma;
static const uint8_t own[6] = {2,0x55,0x50,0x32,0,2}, peer[6] = {2,0x55,0x50,0x33,0,3};
static uint32_t lease, ready, injected, responses, txSlot, rxSlot, nonce, life, pendingTx;
static uint64_t ms;
static unsigned acquireCalls, stopCalls, timerAcquires, writes;
static int acquireResult = 1, startResult = 1, stopResult = 1;
static int noPeer, frozen, badFcs, badBody, badNonce, duplicate, txError, dmaFatal, truncated, badMode;
static int isr, masked, taskOk = 1;
static M7EthHardware regs;
int m7_plk_task_id(uint32_t* task) { *task = 6; return taskOk; }
int m7_plk_in_interrupt(void) { return isr; }
int m7_plk_irq_enabled(void) { return !masked; }
uintptr_t m7_plk_irq_save(void) { int old = masked; masked = 1; return (uintptr_t)old; }
void m7_plk_irq_restore(uintptr_t old) { masked = (int)old; }
uint64_t m7_plk_milliseconds(void) { return frozen ? 0 : ms; }
uint64_t m7_plk_timer_now(void) { return 0x35720001U; }
int m7_hrestimer_active(void) { return 0; }
int m7_plk_timer_acquire(uint32_t* f) { (void)f; ++timerAcquires; assert(0); return 0; }
void m7_plk_timer_mask(void) { assert(0); }
int m7_plk_sem_create(uint16_t* h) { (void)h; assert(0); return 0; }
int m7_plk_sem_take(uint16_t h) { (void)h; assert(0); return 0; }
int m7_plk_sem_give(uint16_t h) { (void)h; assert(0); return 0; }
int m7_plk_sem_delete(uint16_t h) { (void)h; assert(0); return 0; }
int m7_plk_cache(const void* p, size_t n, int inv) { (void)p; (void)n; (void)inv; assert(0); return 0; }
uint32_t m7_eth2_hw_lease(void) { return lease; }
int m7_eth2_hw_acquire(void) { ++acquireCalls; assert(!lease); lease = acquireResult ? 2 : 0; return acquireResult; }
int m7_eth2_hw_start(struct M7Eth2Dma* dma, const uint8_t mac[6])
{
    assert(m7_plk_ready() && dma == &m7_edrv_test_dma && !memcmp(mac, own, 6));
    assert((uintptr_t)dma < UINT32_MAX);
    regs = (M7EthHardware){0}; regs.mac = badMode ? 0xe003 : 0xc003; regs.tx = regs.rx = 1;
    injected = responses = txSlot = rxSlot = ready = pendingTx = 0;
    return startResult;
}
int m7_eth2_hw_stop(void) {
    ++stopCalls; assert(lease == 2);
    if (stopResult) { lease = 0; regs = (M7EthHardware){0}; }
    return stopResult;
}
uint32_t m7_eth2_hw_read(uint32_t offset)
{
    switch (offset) {
        case 0: return regs.mac; case 0x1104: return regs.tx; case 0x1108: return regs.rx;
        case 0x1000: return regs.dma; case 0xb4: return regs.macIrq; case 0x1134: return regs.dmaIrq;
        case 0x1160: return dmaFatal && injected ? 1U << 12 : 0;
        default: assert(0); return 0;
    }
}
void m7_eth2_hw_write(uint32_t offset, uint32_t value)
{
    ++writes; assert(m7_plk_ready());
    if (offset == 0x1160 || offset == 0x1128) return;
    assert(offset == 0x1120 && !pendingTx && responses < M7_EDRV_PROBE_TOTAL);
    assert(value == (uint32_t)(uintptr_t)&m7_edrv_test_dma.tx[(txSlot + 1) % 8]);
    assert(m7_edrv_test_dma.tx[txSlot].d[3] & M7_ETH2_OWN);
    assert(M7ProbeValid(m7_edrv_test_dma.txbuf[0], M7ProbeLength(responses), nonce, responses, 2));
    assert(!memcmp(m7_edrv_test_dma.txbuf[0], peer, 6) && !memcmp(m7_edrv_test_dma.txbuf[0] + 6, own, 6));
    pendingTx = 1; life = 2; ++responses;
}
int PRT_Printf(const char* format, ...)
{
    va_list args; assert(strstr(format, "READY nonce=")); va_start(args, format);
    nonce = va_arg(args, uint32_t); va_end(args); ready = 1; return 0;
}
int m7_plk_sleep(uint32_t delay)
{
    uint8_t* packet; uint32_t length, crc, seq;
    assert(delay == 1 && m7_plk_ready() && !masked && !isr); ++ms;
    if (pendingTx && !--life) {
        m7_edrv_test_dma.tx[txSlot].d[3] = txError ? M7_ETH2_ERROR : 0;
        txSlot = (txSlot + 1) % 8; pendingTx = 0;
    }
    /* Simulate wire RX of the next request before prior TX descriptor completion. */
    if (ready && !noPeer && injected <= responses && injected < M7_EDRV_PROBE_TOTAL) {
        assert(m7_edrv_test_dma.rx[rxSlot].d[3] & M7_ETH2_OWN);
        length = M7ProbeLength(injected); packet = m7_edrv_test_dma.rxbuf[rxSlot];
        seq = duplicate && injected ? 0 : injected;
        M7ProbeFrame(packet, own, peer, badNonce ? nonce + 1 : nonce, seq, 1);
        if (badBody) packet[length - 1] ^= 1;
        crc = EthCrc(packet, length);
        packet[length] = (uint8_t)crc; packet[length+1] = (uint8_t)(crc >> 8);
        packet[length+2] = (uint8_t)(crc >> 16); packet[length+3] = (uint8_t)(crc >> 24);
        if (badFcs) packet[length] ^= 1;
        m7_edrv_test_dma.rx[rxSlot].d[3] = M7_ETH2_FIRST_LAST | (length + (truncated ? 0U : 4U));
        ++injected; rxSlot = (rxSlot + 1) % 8;
    }
    return 1;
}
int main(int argc, char** argv)
{
    M7EdrvProbeResult out; uint32_t expected = M7_EPROBE_OK;
    assert(argc == 2 && m7_edrv_probe(NULL) == M7_EPROBE_CONTEXT);
    if (!strcmp(argv[1], "vector")) {
        uint8_t packet[1514]; unsigned seq, i;
        for (seq = 0; seq <= 32; seq += 32) {
            M7ProbeFrame(packet, own, peer, 0x35720001, seq, 1);
            for (i = 0; i < M7ProbeLength(seq); ++i) printf("%02x", packet[i]);
            putchar('\n');
        }
        return 0;
    }
    if (!strcmp(argv[1], "normal")) {
        unsigned i;
        for (i = 0; i < 10; ++i) {
            assert(!m7_edrv_probe(&out) && out.clean && !lease && !m7_plk_owner());
            assert(out.received == 64 && out.submitted == 64 && out.completed == 64 && out.fcs == 64);
            assert(responses == 64 && out.active.mac == 0xc003 && !out.stopped.mac);
        }
        assert(stopCalls == 10 && !timerAcquires); puts("P3e real EDRV/probe native PASS"); return 0;
    }
    if (!strcmp(argv[1], "no_peer")) noPeer = 1, expected = M7_EPROBE_TIMEOUT;
    else if (!strcmp(argv[1], "frozen")) noPeer = frozen = 1, expected = M7_EPROBE_TIMEOUT;
    else if (!strcmp(argv[1], "fcs")) badFcs = 1, expected = M7_EPROBE_FCS;
    else if (!strcmp(argv[1], "body")) badBody = 1, expected = M7_EPROBE_FRAME;
    else if (!strcmp(argv[1], "nonce")) badNonce = 1, expected = M7_EPROBE_FRAME;
    else if (!strcmp(argv[1], "duplicate")) duplicate = 1, expected = M7_EPROBE_FRAME;
    else if (!strcmp(argv[1], "truncated")) truncated = 1, expected = M7_EPROBE_FRAME;
    else if (!strcmp(argv[1], "tx_error")) txError = 1, expected = M7_EPROBE_POLL;
    else if (!strcmp(argv[1], "dma_fatal")) dmaFatal = 1, expected = M7_EPROBE_POLL;
    else if (!strcmp(argv[1], "mode")) badMode = 1, expected = M7_EPROBE_MODE;
    else if (!strcmp(argv[1], "acquire")) acquireResult = 0, expected = M7_EPROBE_INIT;
    else if (!strcmp(argv[1], "start")) startResult = 0, expected = M7_EPROBE_INIT;
    else if (!strcmp(argv[1], "unsafe_acquire")) acquireResult = -1, expected = M7_EPROBE_CLEANUP;
    else if (!strcmp(argv[1], "unsafe_start")) startResult = stopResult = 0, expected = M7_EPROBE_CLEANUP;
    else if (!strcmp(argv[1], "unsafe_stop")) stopResult = 0, expected = M7_EPROBE_CLEANUP;
    else if (!strcmp(argv[1], "context")) {
        isr = 1; assert(m7_edrv_probe(&out) == M7_EPROBE_CONTEXT); isr = 0;
        masked = 1; assert(m7_edrv_probe(&out) == M7_EPROBE_CONTEXT); masked = 0;
        taskOk = 0; assert(m7_edrv_probe(&out) == M7_EPROBE_CONTEXT); taskOk = 1;
        lease = 1; assert(m7_edrv_probe(&out) == M7_EPROBE_CONTEXT);
        assert(!acquireCalls && !writes && !timerAcquires); puts("P3e context native PASS"); return 0;
    } else assert(0);
    assert(m7_edrv_probe(&out) == expected && !timerAcquires);
    if (expected == M7_EPROBE_CLEANUP) {
        unsigned previous = stopCalls;
        assert(!out.clean && lease == 2 && m7_plk_owner() && m7_plk_faulted());
        assert(m7_edrv_probe(&out) == M7_EPROBE_CONTEXT && stopCalls == previous);
        assert(stopCalls == (acquireResult < 0 ? 0U : 1U));
    } else assert(out.clean && !lease && !m7_plk_owner());
    puts("P3e real EDRV/probe fault native PASS"); return 0;
}
