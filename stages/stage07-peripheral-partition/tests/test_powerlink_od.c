/* Real upstream object-dictionary writes; no network, hardware or floats. */
#include <assert.h>
#include <stdio.h>
#include <user/obdu.h>

static tOplkError access_callback(tObdCbParam* parameter, BOOL user_event)
{
    (void)parameter;
    (void)user_event;
    return kErrorOk;
}

int main(void)
{
    const UINT32 integer_range[] = {5, 1, 10};
    /* IEEE bit patterns: defaults, lower bound, upper bound. No FP instructions. */
    const UINT32 real32_range[] = {0x3f800000U, 0, 0x40000000U};
    const UINT64 real64_range[] = {0x3ff0000000000000ULL, 0, 0x4000000000000000ULL};
    UINT32 integer = 0, real32 = 0, raw32 = 0;
    UINT64 real64 = 0;
    tObdSubEntry subs[] = {
        {0, kObdTypeUInt32, kObdAccGRW, integer_range, &integer},
        {0, kObdTypeReal32, kObdAccGRW, real32_range, &real32},
        {0, kObdTypeReal64, kObdAccGRW, real64_range, &real64},
        {0, kObdTypeReal32, kObdAccRW, real32_range, &raw32},
    };
    tObdEntry empty[] = {{OBD_TABLE_INDEX_END, NULL, 0, FALSE}};
    tObdEntry manufacturer[] = {
        {0x2000, &subs[0], 1, FALSE}, {0x2001, &subs[1], 1, FALSE},
        {0x2002, &subs[2], 1, FALSE}, {0x2003, &subs[3], 1, FALSE},
        {OBD_TABLE_INDEX_END, NULL, 0, FALSE},
    };
    tObdInitParam init = {0};
    init.pGenericPart = empty;
    init.pManufacturerPart = manufacturer;
    init.pDevicePart = empty;
    assert(obdu_init(&init, access_callback) == kErrorOk);
    assert(integer == 5 && real32 == real32_range[0] && real64 == real64_range[0]);
    UINT32 value = 10;
    assert(obdu_writeEntry(0x2000, 0, &value, sizeof(value)) == kErrorOk);
    assert(integer == 10);
    value = 11;
    assert(obdu_writeEntry(0x2000, 0, &value, sizeof(value)) == kErrorObdValueTooHigh);
    assert(integer == 10);
    value = 0;
    assert(obdu_writeEntry(0x2000, 0, &value, sizeof(value)) == kErrorObdValueTooLow);
    assert(integer == 10);
    assert(obdu_writeEntry(0x2001, 0, &real32_range[2], sizeof(UINT32)) == kErrorObdUnknownObjectType);
    assert(obdu_writeEntry(0x2002, 0, &real64_range[2], sizeof(UINT64)) == kErrorObdUnknownObjectType);
    assert(real32 == real32_range[0] && real64 == real64_range[0]);
    assert(obdu_writeEntry(0x2003, 0, &real32_range[2], sizeof(UINT32)) == kErrorOk);
    assert(raw32 == real32_range[2]);
    assert(obdu_exit() == kErrorOk);
    puts("PASS: integer range bounds; ranged REAL32/64 rejected unchanged; raw REAL32 bytes preserved");
    return 0;
}
