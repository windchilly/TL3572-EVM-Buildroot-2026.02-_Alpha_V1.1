#include <assert.h>
#include <stdio.h>
#include "../source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_can_fd_codec.h"

int main(void)
{
    const uint8_t lengths[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64};
    uint8_t bytes[64], decoded[64];
    unsigned i, brp, tseg1, tseg2;
    for (i = 0; i < 16; i++) {
        assert(RkCanFdDlcToLength(i) == lengths[i]);
        assert(RkCanFdLengthToDlc(lengths[i]) == i);
        assert(RkCanFdTxInfo(lengths[i], 0) == (i | 0x20U));
        assert(RkCanFdTxInfo(lengths[i], 1) == (i | 0x30U));
    }
    for (i = 0; i < 256; i++) {
        uint8_t dlc = RkCanFdLengthToDlc(i);
        if (dlc != 0xFFU) { assert(RkCanFdDlcToLength(dlc) == i); }
        else { assert(RkCanFdTxInfo(i, 0) == 0xFFFFFFFFU); }
    }
    assert(RkCanFdDlcToLength(16) == 0xFFU);
    assert(RkCanFdMatchesRxFlags(0x0F200000U, 0));
    assert(RkCanFdMatchesRxFlags(0x0F300000U, 1));
    assert(!RkCanFdMatchesRxFlags(0x0F200000U, 1));
    assert(!RkCanFdMatchesRxFlags(0x0F300000U, 0));
    assert(!RkCanFdMatchesRxFlags(0x0F000000U, 0));
    assert(!RkCanFdMatchesRxFlags(0x0FA00000U, 0));
    assert(!RkCanFdMatchesRxFlags(0x0F600000U, 0));
    for (i = 0; i < 64; i++) { bytes[i] = (uint8_t)(i * 17); }
    for (i = 0; i < 64; i += 4) { RkCanFdUnpackWord(RkCanFdPackWord(bytes + i), decoded + i); }
    for (i = 0; i < 64; i++) { assert(decoded[i] == bytes[i]); }
    brp = 2 * (((RK_CAN_FD_NBTP >> 16) & 255) + 1);
    tseg1 = (RK_CAN_FD_NBTP & 255) + 1; tseg2 = ((RK_CAN_FD_NBTP >> 8) & 127) + 1;
    assert(297000000U / (brp * (1 + tseg1 + tseg2)) == 500000U);
    brp = 2 * (((RK_CAN_FD_DBTP2 >> 9) & 255) + 1);
    tseg1 = (RK_CAN_FD_DBTP2 & 31) + 1; tseg2 = ((RK_CAN_FD_DBTP2 >> 5) & 15) + 1;
    assert(tseg1 == 27 && tseg2 == 9 && brp == 4);
    assert(297000000U / (brp * (1 + tseg1 + tseg2)) == 2006756U);
    assert((RK_CAN_FD_DBTP2 >> 24) == (tseg1 - 1) / 2);
    brp = 2 * (((RK_CAN_FD_DBTP4 >> 9) & 255) + 1);
    assert(297000000U / (brp * (1 + tseg1 + tseg2)) == 4013513U);
    assert(RK_CAN_FD_TDCR4 == (((1 + tseg1) * (brp / 2) - 2) << 1 | 1U));
    puts("CAN FD CODEC PASS: DLC, flags, 64-byte words, NBTP/DBTP/TDC");
    return 0;
}
