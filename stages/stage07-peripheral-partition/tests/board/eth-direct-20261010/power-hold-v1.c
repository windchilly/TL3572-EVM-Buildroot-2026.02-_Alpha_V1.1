// SPDX-License-Identifier: GPL-2.0-only
/* Temporary shared-fabric power reference. No MAC/MDIO/clock/pin/DMA access. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>

static struct platform_device *hold;

static int __init m7_hold_init(void)
{
    struct device *mac;
    struct generic_pm_domain *domain;
    int rc;
    mac = bus_find_device_by_name(&platform_bus_type, NULL, "2a040000.ethernet");
    if (!mac)
        return -ENODEV;
    if (!mac->driver || !mac->pm_domain) {
        put_device(mac);
        return -EBUSY;
    }
    domain = pd_to_genpd(mac->pm_domain);
    if (strcmp(domain->name, "nvm0")) {
        put_device(mac);
        return -EINVAL;
    }
    hold = platform_device_register_simple("m7-eth2-power-hold", -1, NULL, 0);
    if (IS_ERR(hold)) {
        rc = PTR_ERR(hold);
        put_device(mac);
        return rc;
    }
    rc = pm_genpd_add_device(domain, &hold->dev);
    put_device(mac);
    if (rc)
        goto unregister;
    pm_runtime_enable(&hold->dev);
    rc = pm_runtime_resume_and_get(&hold->dev);
    if (rc < 0) {
        pm_runtime_disable(&hold->dev);
        pm_genpd_remove_device(&hold->dev);
        goto unregister;
    }
    pr_info("M7 ETH2 shared nvm0 power held; MAC remains independently owned\n");
    return 0;
unregister:
    platform_device_unregister(hold);
    return rc;
}

static void __exit m7_hold_exit(void)
{
    /* Host runner must first quiesce UP2 DMA, stop CPU5, and rebind Linux. */
    pm_runtime_put_sync(&hold->dev);
    pm_runtime_disable(&hold->dev);
    pm_genpd_remove_device(&hold->dev);
    platform_device_unregister(hold);
    pr_info("M7 ETH2 shared nvm0 power reference released\n");
}
module_init(m7_hold_init);
module_exit(m7_hold_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary RK3572 ETH2 shared NVM0 power hold for UP2 handoff");
