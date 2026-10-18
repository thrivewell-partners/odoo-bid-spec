from . import models
from . import wizard


def post_init_hook(env):
    # The column is made before the module's data, so its default could not name the shipped reason.
    reason = env.ref("twp_bid_spec.lost_reason_cancelled")
    env["res.company"].search([("twp_bs_cancelled_reason_id", "=", False)]).twp_bs_cancelled_reason_id = reason
