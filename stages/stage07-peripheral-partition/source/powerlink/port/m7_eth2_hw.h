/* UP2-only GMAC1 DMA contract. Identity-mapped Normal-NC, shared, RW/XN DDR. */
#ifndef M7_ETH2_HW_H
#define M7_ETH2_HW_H
#include <stdint.h>
#define M7_ETH2_RING 8U
#define M7_ETH2_TX_BUFFERS 32U
#define M7_ETH2_BUFFER_SIZE 1536U
#define M7_ETH2_DMA_ADDRESS 0x7ca10000UL
#define M7_ETH2_OWN (1U << 31)
#define M7_ETH2_FIRST_LAST 0x30000000U
#define M7_ETH2_ERROR (1U << 15)
struct M7Eth2Desc { volatile uint32_t d[4]; };
struct M7Eth2Dma {
    struct M7Eth2Desc tx[M7_ETH2_RING], rx[M7_ETH2_RING];
    uint8_t txbuf[M7_ETH2_TX_BUFFERS][M7_ETH2_BUFFER_SIZE];
    uint8_t rxbuf[M7_ETH2_RING][M7_ETH2_BUFFER_SIZE];
};
/* C99 compatible, also checked by native tests. No cached alias is permitted. */
typedef char M7Eth2DmaFits[(sizeof(struct M7Eth2Dma) <= 0x10000U) ? 1 : -1];
static inline void m7_eth2_dma_barrier(void)
{
#if defined(__aarch64__)
    __asm__ volatile("dsb sy" ::: "memory");
#else
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
#endif
}
/* acquire: 1 ready, 0 safely stopped/refused, -1 unsafe (retain host hold).
 * DMA memory must not be touched before successful acquire. RX retains FCS.
 * start is called only after the driver has initialized every descriptor.
 * stop: 1 reset proven, 0 unsafe; NEVER release host power on unsafe return.
 */
int m7_eth2_hw_acquire(void);
int m7_eth2_hw_start(struct M7Eth2Dma* dma, const uint8_t mac[6]);
int m7_eth2_hw_stop(void);
uint32_t m7_eth2_hw_read(uint32_t offset);
void m7_eth2_hw_write(uint32_t offset, uint32_t value);
#endif
