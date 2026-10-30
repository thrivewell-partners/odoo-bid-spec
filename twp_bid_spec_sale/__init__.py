from . import models
from . import wizard


def post_init_hook(env):
    """Every product line gets its Sales product now, so a bid can carry it before the catalog is in."""
    for line in env["twp.bid.spec.product.line"].with_context(active_test=False).search([]):
        line._twp_bs_sale_product()


def uninstall_hook(env):
    """Sales' Bids menu goes back beside Quotations."""
    menu = env.ref("twp_bids.menu_bids", raise_if_not_found=False)
    parent = env.ref("sale.sale_order_menu", raise_if_not_found=False)
    if menu and parent:
        menu.write({"name": "Bids", "parent_id": parent.id, "sequence": 5})
