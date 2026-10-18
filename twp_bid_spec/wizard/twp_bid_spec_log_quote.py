from datetime import timedelta

from odoo import _, api, fields, models

from ..models.twp_bid_spec_quote import QUOTED_AS


def _next_follow_up(wizard):
    return fields.Date.context_today(wizard) + timedelta(days=wizard.env.company.twp_bs_followup_days)


class TwpBidSpecLogQuote(models.TransientModel):
    """Record a contractor contact on a job, with or without a bid, and set the next follow-up."""

    _name = "twp.bid.spec.log.quote"
    _description = "Log a bid"

    lead_id = fields.Many2one("crm.lead", required=True, readonly=True)
    product_line_id = fields.Many2one("twp.bid.spec.product.line", string="Product line", required=True)
    partner_id = fields.Many2one("res.partner", string="Contractor", required=True)
    source_id = fields.Many2one("twp.bid.spec.source", string="Bid source")
    quoted_as = fields.Selection(QUOTED_AS, string="Bid as")
    user_id = fields.Many2one("res.users", string="Bid by", default=lambda self: self.env.user)
    quoted = fields.Boolean("Bid sent", default=True, help="Off: we contacted them but have not sent a bid yet.")
    date = fields.Date(required=True, default=fields.Date.context_today)
    model_quoted = fields.Char("Model we bid")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary("Bid $")
    margin = fields.Float("Margin %")
    next_date = fields.Date("Next follow-up", default=_next_follow_up)
    note = fields.Text()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead = self.env["crm.lead"].browse(res.get("lead_id") or self.env.context.get("active_id"))
        if len(lead.twp_bs_job_ids) == 1 and "product_line_id" in fields_list:
            res["product_line_id"] = lead.twp_bs_job_ids.product_line_id.id
        return res

    def action_apply(self):
        self.ensure_one()
        Job = self.env["twp.bid.spec.job"]
        job = Job.search([("lead_id", "=", self.lead_id.id), ("product_line_id", "=", self.product_line_id.id)])
        if not job:
            job = Job.create({"lead_id": self.lead_id.id, "product_line_id": self.product_line_id.id})
        quote = job.quote_ids.filtered(lambda q: q.partner_id == self.partner_id)[:1]
        vals = {"last_contact_date": self.date, "user_id": self.user_id.id}
        if self.source_id:
            vals["source_id"] = self.source_id.id
        if self.quoted_as:
            vals["quoted_as"] = self.quoted_as
        if self.quoted:
            vals.update(quote_date=self.date, amount=self.amount, margin=self.margin)
            if self.model_quoted:
                vals["model_quoted"] = self.model_quoted
        if not quote:
            quote = self.env["twp.bid.spec.quote"].create({
                "job_id": job.id, "partner_id": self.partner_id.id, "first_contact_date": self.date, **vals})
        else:
            if not quote.first_contact_date:
                vals["first_contact_date"] = self.date
            quote.write(vals)
        body = _("Bid sent: %(amount)s", amount=self._format_amount()) if self.quoted else _("Contacted, no bid yet.")
        quote._twp_bs_touch(body, self.note, self.next_date)
        return {"type": "ir.actions.act_window_close"}

    def _format_amount(self):
        return self.currency_id.format(self.amount) if self.currency_id else str(self.amount)
