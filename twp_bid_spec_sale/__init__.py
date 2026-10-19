from . import models
from . import wizard


def post_init_hook(env):
    """Every product line gets its Sales product now, so a bid can carry it before the catalog is in."""
    for line in env["twp.bid.spec.product.line"].with_context(active_test=False).search([]):
        line._twp_bs_sale_product()
