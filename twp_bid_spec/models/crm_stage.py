from odoo import fields, models

# Where a stage sits in a Bid / Spec project's life. The project's bid status, which RESULT
# reads, follows from it: Review is still Bidding, Closed is still Awarded.
STEPS = [
    ("review", "Review"),
    ("bidding", "Bidding"),
    ("closed", "Bidding Closed"),
    ("awarded", "Awarded"),
    ("done", "Closed"),
]
STATUS_OF_STEP = {
    "review": "bidding",
    "bidding": "bidding",
    "closed": "opened",
    "awarded": "awarded",
    "done": "awarded",
}


class CrmStage(models.Model):
    _inherit = "crm.stage"

    twp_bs_step = fields.Selection(
        STEPS, string="Bid / Spec step",
        help="What this stage means in a Bid / Spec pipeline. Review asks for a review; the nightly "
             "close moves past bids from Bidding to Bidding Closed; Award moves a project to Awarded.",
    )
