from odoo import api, fields, models


class TwpBidSpecQuote(models.Model):
    _inherit = "twp.bid.spec.quote"

    sale_order_id = fields.Many2one(
        "sale.order", string="Bid document", readonly=True, copy=False, index="btree_not_null",
        ondelete="set null", help="The bid built in Sales that this contractor bid comes from.")

    # A bid built in Sales is its own document: it prints from Sales whenever it is wanted.
    @api.depends("quote_date", "document_ids", "sale_order_id")
    def _compute_document_missing(self):
        return super()._compute_document_missing()

    def _twp_bs_has_document(self):
        return super()._twp_bs_has_document() or bool(self.sale_order_id)
