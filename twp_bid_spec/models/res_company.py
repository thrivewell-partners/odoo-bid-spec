from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    twp_bs_bid_date_required = fields.Boolean(
        string="Bid date required", default=True,
        help="A Bid / Spec project cannot be saved without its bid date.",
    )
    twp_bs_close_after_bid_date = fields.Boolean(
        string="Close bidding after the bid date", default=True,
        help="Each night, a card still in a Bidding stage after its bid date moves to its pipeline's "
             "first Bidding Closed stage.",
    )
    twp_bs_followup_days = fields.Integer(
        string="Follow up after", default=7,
        help="Days from logging a bid or a touch to the next follow-up it books.",
    )
    twp_bs_warning_days = fields.Integer(
        string="Warn before the bid date", default=7,
        help="A Bidding card with no bid sent is flagged when its bid date is this many days away or fewer.",
    )
    twp_bs_due_window_days = fields.Integer(
        string="Bids due within", default=14, help="The dashboard's window for bids coming due.",
    )
    twp_bs_cancelled_reason_id = fields.Many2one(
        "crm.lost.reason", string="Cancelled / postponed reason",
        help="The lost reason that means the project was cancelled or postponed, rather than passed at "
             "review. Its bids read Project Dead, and the project still counts in reports.",
    )
    twp_bs_side_lead_team_id = fields.Many2one(
        "crm.team", string="Side leads go to",
        help="The pipeline a side lead spotted at review is parked in. Leave empty to turn side leads off.",
    )
    twp_bs_side_lead_stage_id = fields.Many2one(
        "crm.stage", string="Side lead stage",
        domain="['|', ('team_ids', '=', False), ('team_ids', 'in', twp_bs_side_lead_team_id)]",
    )
