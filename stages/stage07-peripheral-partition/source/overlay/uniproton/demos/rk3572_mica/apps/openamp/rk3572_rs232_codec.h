#ifndef RK3572_RS232_CODEC_H
#define RK3572_RS232_CODEC_H
#include <stdint.h>
#define RS232_FRAME_SIZE 32U
static uint16_t Rs232Crc(const uint8_t *data, uint32_t length)
{
    uint16_t crc = 0xFFFFU;
    uint32_t i, bit;
    for (i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (bit = 0; bit < 8; bit++) {
            crc = (uint16_t)((crc << 1) ^ ((crc & 0x8000U) ? 0x1021U : 0U));
        }
    }
    return crc;
}
static void Rs232Fill(uint8_t *data, uint8_t marker, uint32_t sequence)
{
    uint32_t i;
    uint16_t crc;
    data[0] = 0x55U; data[1] = 0xAAU; data[2] = marker; data[3] = RS232_FRAME_SIZE;
    for (i = 0; i < 4; i++) { data[4 + i] = (uint8_t)(sequence >> (i * 8)); }
    for (i = 8; i < 30; i++) { data[i] = (uint8_t)((sequence * 17U + i * 29U) ^ marker); }
    crc = Rs232Crc(data, 30U); data[30] = (uint8_t)crc; data[31] = (uint8_t)(crc >> 8);
}
static int Rs232Matches(const uint8_t *data, uint8_t marker, uint32_t sequence)
{
    uint8_t expected[RS232_FRAME_SIZE];
    uint32_t i;
    Rs232Fill(expected, marker, sequence);
    for (i = 0; i < RS232_FRAME_SIZE; i++) {
        if (data[i] != expected[i]) { return 0; }
    }
    return 1;
}
#endif
