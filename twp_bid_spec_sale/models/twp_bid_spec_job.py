from odoo import fields, models


class TwpBidSpecJob(models.Model):
    _inherit = "twp.bid.spec.job"

    sale_order_id = fields.Many2one(related="lead_id.twp_bs_sale_order_id")
