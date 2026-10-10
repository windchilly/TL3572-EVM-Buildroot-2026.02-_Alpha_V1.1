// SPDX-License-Identifier: GPL-2.0-only
/* Temporary shared-fabric power/root-clock references. No MAC/MDIO/pin/DMA access. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/of.h>
#include <linux/of_clk.h>
#include <linux/clk.h>
#include <linux/clk-provider.h>

static struct platform_device *hold;
static struct clk *fabric[2];

static void release_fabric(void)
{
    int i;
    for (i = 1; i >= 0; i--) {
        if (fabric[i]) {
            clk_disable_unprepare(fabric[i]);
            clk_put(fabric[i]);
            fabric[i] = NULL;
        }
    }
}

static int hold_root(struct device *mac, const char *leaf_name,
                     const char *root_name, int index)
{
    struct clk *leaf, *parent, *root;
    int rc;
    leaf = of_clk_get_by_name(mac->of_node, leaf_name);
    if (IS_ERR(leaf))
        return PTR_ERR(leaf);
    parent = clk_get_parent(leaf); /* Borrowed core clock, do not clk_put(parent). */
    if (!parent || strcmp(__clk_get_name(parent), root_name)) {
        clk_put(leaf);
        return -EINVAL;
    }
    /* Own a consumer reference to the shared parent, never to a MAC leaf. */
    root = clk_hw_get_clk(__clk_get_hw(parent), "m7-eth2-shared-fabric");
    clk_put(leaf);
    if (IS_ERR(root))
        return PTR_ERR(root);
    rc = clk_prepare_enable(root);
    if (rc) {
        clk_put(root);
        return rc;
    }
    fabric[index] = root;
    pr_info("M7 shared fabric %s held at %lu Hz; no rate/parent changes\n",
            root_name, clk_get_rate(root));
    return 0;
}

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
    hold = platform_device_alloc("m7-eth2-power-hold", -1);
    if (!hold) {
        put_device(mac);
        return -ENOMEM;
    }
    /* Rockchip attach_dev unconditionally calls of_clk_get(dev->of_node).
     * Supply a real, clockless node: using the MAC node would hold MAC clocks
     * and wrongly make the Linux helper participate in the runtime driver.
     * The platform-device release path owns and drops this node reference.
     */
    hold->dev.of_node = of_find_node_by_path("/chosen");
    if (!hold->dev.of_node || of_find_property(hold->dev.of_node, "clocks", NULL)) {
        platform_device_put(hold);
        put_device(mac);
        return -EINVAL;
    }
    rc = platform_device_add(hold);
    if (rc) {
        platform_device_put(hold);
        put_device(mac);
        return rc;
    }
    rc = pm_genpd_add_device(domain, &hold->dev);
    if (rc)
        goto unregister;
    pm_runtime_enable(&hold->dev);
    rc = pm_runtime_resume_and_get(&hold->dev);
    if (rc < 0) {
        pm_runtime_disable(&hold->dev);
        pm_genpd_remove_device(&hold->dev);
        goto unregister;
    }
    rc = hold_root(mac, "aclk_mac", "aclk_nvm0_root", 0);
    if (!rc)
        rc = hold_root(mac, "pclk_mac", "pclk_nvm0_root", 1);
    if (rc) {
        release_fabric();
        pm_runtime_put_sync(&hold->dev);
        pm_runtime_disable(&hold->dev);
        pm_genpd_remove_device(&hold->dev);
        goto unregister;
    }
    put_device(mac);
    pr_info("M7 ETH2 shared nvm0 power/fabric held; MAC remains independently owned\n");
    return 0;
unregister:
    put_device(mac);
    platform_device_unregister(hold);
    return rc;
}

static void __exit m7_hold_exit(void)
{
    /* Host runner must first quiesce UP2 DMA, stop CPU5, and rebind Linux. */
    release_fabric();
    pm_runtime_put_sync(&hold->dev);
    pm_runtime_disable(&hold->dev);
    pm_genpd_remove_device(&hold->dev);
    platform_device_unregister(hold);
    pr_info("M7 ETH2 shared nvm0 power reference released\n");
}
module_init(m7_hold_init);
module_exit(m7_hold_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary RK3572 ETH2 shared NVM0 power/fabric hold for UP2 handoff");
