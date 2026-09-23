#ifndef CPU_CONFIG_H
#define CPU_CONFIG_H

#include "cache_asm.h"

/*
 * TL3572 (RK3572) board config for one UniProton MICA instance.
 *
 * SoC facts (vendor rk3572.dtsi / tl3572-evm.dts, verified 2026-09-17):
 *   - interrupt controller: arm,gic-400 (GICv2), GICD 0x2a601000,
 *     GICC 0x2a602000 (GICH 0x2a604000, GICV 0x2a606000 unused here);
 *   - M6 assigns CPU4/SGI8 to UP-A and CPU5/SGI9 to UP-B;
 *   - debug UART = uart0 @ 0x2c130000 (earlycon uart8250,mmio32, 115200,
 *     already configured by the Linux side console);
 *   - instance memory = mcs-rmem@7a000000, 64 MiB, no-map:
 *       0x7a000000 +0x100000  MCS per-CPU shared pools (8 x 128 KiB)
 *       CPU4 pool: 0x7a080000 +0x020000; image: 0x7b200000 +0x800000;
 *       CPU5 pool: 0x7a0a0000 +0x020000; image: 0x7c200000 +0x800000;
 *       each instance keeps its MMU tables in the final 6 MiB of its slice.
 *   - Linux owns SGIs 0-7; mcs_km claims SGI8 and SGI9 for the two clients.
 *
 * GICv2 macro set follows demos/raspi4 (BCM2711 GIC-400, the only
 * OS_GIC_VER==2 reference in tree); generic macros kept from demos/rk3588.
 */

#define UART_BASE_ADDR          0x2C130000ULL
#define MMU_UART_ADDR           0x2C130000ULL

#ifndef MMU_IMAGE_ADDR
#define MMU_IMAGE_ADDR          0x7C200000ULL
#endif
#define MMU_GIC_ADDR            0x2A600000ULL
#define MMU_OPENAMP_ADDR        0x7A000000ULL

#define OPENAMP_SHARED_MEM_LENGTH   0x2000000U
#define OPENAMP_LOG_LENGTH          0x200000U

/* mcs/library/remoteproc/baremetal_rproc.c: 128 KiB per CPU. */
#define MCS_SHM_POOL_SIZE           0x20000U
#ifndef MCS_CLIENT_CPU_ID
#define MCS_CLIENT_CPU_ID           5U
#endif
#ifndef MCS_NOTIFY_SGI_ID
#define MCS_NOTIFY_SGI_ID           8U
#endif
#define OPENAMP_VDEV_ADDR           (MMU_OPENAMP_ADDR + \
                                     MCS_CLIENT_CPU_ID * MCS_SHM_POOL_SIZE)
#define OPENAMP_VDEV_SIZE           MCS_SHM_POOL_SIZE

#define TEST_CLK_INT            27  /* PPI 11: CNTV line, verified by GICD_ISPENDR0 bit27 */

#define OS_GIC_VER              2
#define SICR_ADDR_OFFSET_PER_CORE 0x200U

#define GIC_REG_BASE_ADDR       0x2A601000ULL    /* GICD */

#define GIC_DIST_BASE           GIC_REG_BASE_ADDR
#define GIC_CPU_BASE            (GIC_DIST_BASE + 0x1000U)

#define GICD_CTLR               (GIC_DIST_BASE + 0x0000U)
#define GICD_TYPER              (GIC_DIST_BASE + 0x0004U)
#define GICD_IIDR               (GIC_DIST_BASE + 0x0008U)
#define GICD_IGROUPRn           (GIC_DIST_BASE + 0x0080U)
#define GICD_ISENABLERn         (GIC_DIST_BASE + 0x0100U)
#define GICD_ICENABLERn         (GIC_DIST_BASE + 0x0180U)
#define GICD_ISPENDRn           (GIC_DIST_BASE + 0x0200U)
#define GICD_ICPENDRn           (GIC_DIST_BASE + 0x0280U)
#define GICD_ISACTIVERn         (GIC_DIST_BASE + 0x0300U)
#define GICD_ICACTIVERn         (GIC_DIST_BASE + 0x0380U)
#define GICD_IPRIORITYn         (GIC_DIST_BASE + 0x0400U)
#define GICD_ITARGETSRn         (GIC_DIST_BASE + 0x0800U)
#define GICD_SGIR               (GIC_DIST_BASE + 0x0F00U)

#define GICC_CTLR               (GIC_CPU_BASE + 0x0000U)
#define GICC_PMR                (GIC_CPU_BASE + 0x0004U)
#define GICC_IAR                (GIC_CPU_BASE + 0x000CU)
#define GICC_EOIR               (GIC_CPU_BASE + 0x0010U)

#define MAX_INT_NUM             384
#define MIN_GIC_SPI_NUM         32
#define SICD_IGROUP_INT_NUM     32
#define SICD_REG_SIZE           4

#define GROUP_MAX_BPR           0x7U
#define GROUP0_BP               0
#define GROUP1_BP               0

#define PRIO_MASK_LEVEL         0xFFU

#define BIT(n)                  (1 << (n))

#define GICC_CTLR_ENABLEGRP0    BIT(0)
#define GICC_CTLR_ENABLEGRP1    BIT(1)
#define GICC_CTLR_FIQBYPDISGRP0 BIT(5)
#define GICC_CTLR_IRQBYPDISGRP0 BIT(6)
#define GICC_CTLR_FIQBYPDISGRP1 BIT(7)
#define GICC_CTLR_IRQBYPDISGRP1 BIT(8)

#define GICC_CTLR_ENABLE_MASK   (GICC_CTLR_ENABLEGRP0 | \
                                 GICC_CTLR_ENABLEGRP1)

#define GICC_CTLR_BYPASS_MASK   (GICC_CTLR_FIQBYPDISGRP0 | \
                                 GICC_CTLR_IRQBYPDISGRP0 | \
                                 GICC_CTLR_FIQBYPDISGRP1 | \
                                GICC_CTLR_IRQBYPDISGRP1)

#define PARAS_TO_STRING(x...)   #x
#define REG_ALIAS(x...)         PARAS_TO_STRING(x)

#define GIC_REG_READ(addr)      (*(volatile U32 *)((uintptr_t)(addr)))
#define GIC_REG_WRITE(addr, data) (*(volatile U32 *)((uintptr_t)(addr)) = (U32)(data))

#endif
