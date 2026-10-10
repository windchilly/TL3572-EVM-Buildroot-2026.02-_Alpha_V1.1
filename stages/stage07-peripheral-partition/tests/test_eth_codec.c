#include <assert.h>
#include <stdio.h>
#include "rk3572_eth_codec.h"
int main(void)
{
    uint8_t p[1514] = {0};
    uint32_t lengths[] = {64U, 1514U}, n, seq, i, bit;
    assert(EthCrc((const uint8_t *)"123456789", 9) == 0xcbf43926U);
    for (n = 0; n < 2; n++) {
        uint32_t length = lengths[n];
        for (seq = 0; seq < 1000U; seq++) {
            p[12] = 0x88U; p[13] = 0xb5U; memcpy(p + 14, "M7ETH3L2", 8);
            EthPut32(p + 22, 1U); EthPut32(p + 26, seq); EthPut32(p + 30, length - 38U);
            for (i = 0; i < length - 38U; i++) { p[34U + i] = (uint8_t)(seq + i); }
            EthPut32(p + length - 4U, EthCrc(p + 14, length - 18U));
            assert(EthValidate(p, length, seq, 1U));
            assert(!EthValidate(p, length, seq + 1U, 1U));
            assert(!EthValidate(p, length, seq, 2U));
        }
        for (i = 14; i < length; i++) {
            for (bit = 0; bit < 8; bit++) {
                p[i] ^= 1U << bit; assert(!EthValidate(p, length, 999U, 1U)); p[i] ^= 1U << bit;
            }
        }
    }
    puts("ETH CODEC PASS: CRC vector, 2000 sequences, roles and every payload/CRC bit corruption");
    return 0;
}
