/* Compile-only geometry from actual pinned upstream private PDO types.
 * Include via -I $OPLK_SOURCE/stack/src; never linked into firmware. */
#include <stddef.h>
#include <stdint.h>
#include "user/pdo/pdou.c"
const uint32_t m7_pdo_geometry[] = {
    sizeof(tPdoMappObject), D_PDO_RPDOChannelObjects_U8, D_PDO_TPDOChannelObjects_U8,
    sizeof(tPdoChannel), sizeof(tPdouInstance), offsetof(tPdouInstance, pdoChannels),
    offsetof(tPdouInstance, pdoChannels.allocation.rxPdoChannelCount),
    offsetof(tPdouInstance, pdoChannels.allocation.txPdoChannelCount),
    offsetof(tPdouInstance, paRxObject), offsetof(tPdouInstance, paTxObject)
};
