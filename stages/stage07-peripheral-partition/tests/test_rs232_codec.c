#include <assert.h>
#include <stdio.h>
#include "rk3572_rs232_codec.h"
int main(void)
{
    uint8_t frame[RS232_FRAME_SIZE];
    uint32_t sequence, byte, bit;
    assert(Rs232Crc((const uint8_t *)"123456789", 9) == 0x29B1U);
    for (sequence = 0; sequence < 1000; sequence++) {
        Rs232Fill(frame, 'A', sequence);
        assert(Rs232Matches(frame, 'A', sequence));
        assert(!Rs232Matches(frame, 'B', sequence));
        assert(!Rs232Matches(frame, 'A', sequence + 1));
        for (byte = 0; byte < RS232_FRAME_SIZE; byte++) {
            for (bit = 0; bit < 8; bit++) {
                frame[byte] ^= (uint8_t)(1U << bit);
                assert(!Rs232Matches(frame, 'A', sequence));
                frame[byte] ^= (uint8_t)(1U << bit);
            }
        }
    }
    puts("RS232 codec PASS: CRC vector, 1000 sequences, wrong role/sequence, 256000 bit mutations");
    return 0;
}
