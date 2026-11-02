from odoo import fields, models


class TwpBidSpecQuote(models.Model):
    _inherit = "twp.bid.spec.quote"

    sale_order_id = fields.Many2one(
        "sale.order", string="Bid document", readonly=True, copy=False, index="btree_not_null",
        ondelete="set null", help="The bid built in Sales that this contractor bid comes from.")
    sale_order_is_bid = fields.Boolean(related="sale_order_id.twp_is_bid")

    def action_twp_bs_duplicate(self):
        """Duplicate for Contractor on the bid document this contractor bid comes from."""
        self.ensure_one()
        return self.sale_order_id.action_twp_copy_to_customers()
