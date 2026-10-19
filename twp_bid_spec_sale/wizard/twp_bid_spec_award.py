from odoo import _, models


class TwpBidSpecAward(models.TransientModel):
    """A project won by a buyer we bid to gets one Sales quotation, for that buyer's bid."""

    _inherit = "twp.bid.spec.award"

    def _twp_bs_after_award(self):
        super()._twp_bs_after_award()
        self.lead_id._twp_bs_sync_sale_order()

    def _twp_bs_winner_label(self):
        winner = super()._twp_bs_winner_label()
        order = self.lead_id.twp_bs_sale_order_id.filtered(lambda o: o.state != "cancel")
        if order:
            winner = _("%(winner)s, quotation %(order)s", winner=winner, order=order.name)
        return winner
