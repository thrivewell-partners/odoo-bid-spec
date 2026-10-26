from odoo import fields, models


class TwpBidSpecQuote(models.Model):
    _inherit = "twp.bid.spec.quote"

    sale_order_id = fields.Many2one(
        "sale.order", string="Bid document", readonly=True, copy=False, index="btree_not_null",
        ondelete="set null", help="The bid built in Sales that this contractor bid comes from.")
