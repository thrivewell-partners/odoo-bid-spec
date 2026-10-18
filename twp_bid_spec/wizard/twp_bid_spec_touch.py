from odoo import _, fields, models

from .twp_bid_spec_log_quote import _next_follow_up


class TwpBidSpecTouch(models.TransientModel):
    """A follow-up call or email to a contractor about a bid, and when to try next."""

    _name = "twp.bid.spec.touch"
    _description = "Log a touch"

    quote_id = fields.Many2one("twp.bid.spec.quote", string="Bid", required=True, readonly=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    channel = fields.Selection([("call", "Call"), ("email", "Email"), ("visit", "Visit"), ("other", "Other")],
                               default="call", required=True)
    note = fields.Text()
    next_date = fields.Date("Next follow-up", default=_next_follow_up,
                            help="Leave empty when no further follow-up is needed.")

    def action_apply(self):
        self.ensure_one()
        quote = self.quote_id
        vals = {"last_contact_date": max(self.date, quote.last_contact_date or self.date)}
        if not quote.first_contact_date:
            vals["first_contact_date"] = self.date
        quote.write(vals)
        channel = dict(self._fields["channel"].selection)[self.channel]
        quote._twp_bs_touch(_("Touch: %(channel)s on %(date)s", channel=channel, date=self.date),
                            self.note, self.next_date)
        return {"type": "ir.actions.act_window_close"}
