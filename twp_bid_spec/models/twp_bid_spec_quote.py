from markupsafe import Markup

from odoo import _, api, fields, models

RESULTS = [
    ("not_quoted", "Not Bid Yet"),
    ("pending", "Pending"),
    ("project_dead", "Project Dead"),
    ("awarded_update", "Awarded - Update"),
    ("lost_contractor", "Lost - Other Contractor"),
    ("lost_mfr", "Lost - Other Mfr"),
    ("won", "Won"),
]
QUOTED_AS = [
    ("bod", "Basis of Design"),
    ("approved_equal", "Approved Equal"),
    ("substitution", "Substitution / Value Engineering"),
]
# Decided: Won, or any loss. Project Dead and Awarded - Update decide nothing.
DECIDED_RESULTS = ("won", "lost_contractor", "lost_mfr")


class TwpBidSpecQuote(models.Model):
    """One contractor's bid on one job."""

    _name = "twp.bid.spec.quote"
    _description = "Contractor bid"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id"

    job_id = fields.Many2one("twp.bid.spec.job", string="Job", required=True, index=True, ondelete="cascade")
    lead_id = fields.Many2one(related="job_id.lead_id", string="Project", store=True, index=True)
    product_line_id = fields.Many2one(related="job_id.product_line_id", store=True)
    company_id = fields.Many2one(related="job_id.company_id", store=True)
    currency_id = fields.Many2one(related="job_id.currency_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Contractor", required=True, index=True, tracking=True)
    source_id = fields.Many2one("twp.bid.spec.source", string="Bid source")
    source_kind = fields.Selection(related="source_id.kind", string="Outreach", store=True)
    user_id = fields.Many2one("res.users", string="Bid by", default=lambda self: self.env.user, tracking=True)
    model_quoted = fields.Char("Model we bid")
    quoted_as = fields.Selection(QUOTED_AS, string="Bid as")
    first_contact_date = fields.Date("First contact")
    quote_date = fields.Date("Bid sent", tracking=True)
    last_contact_date = fields.Date("Last contact")
    amount = fields.Monetary("Bid $", tracking=True)
    margin = fields.Float("Margin %", help="As a fraction: 0.24 is 24%.")
    gross_profit = fields.Monetary("Gross profit $", compute="_compute_gross_profit", store=True)
    result_override = fields.Selection([
        ("won", "Won"),
        ("lost_contractor", "Lost - Other Contractor"),
        ("lost_mfr", "Lost - Other Mfr"),
        ("project_dead", "Project Dead"),
    ], string="Result override", tracking=True)
    result = fields.Selection(RESULTS, string="Result", compute="_compute_result", store=True, index=True)
    reporting_date = fields.Date("Reporting date", compute="_compute_reporting_date", store=True)
    # The per-line helpers as 1 or 0, so a pivot can add them up.
    quotes_sent = fields.Integer("Bids sent", compute="_compute_counts", store=True)
    quotes_decided = fields.Integer("Bids decided", compute="_compute_counts", store=True)
    quotes_won = fields.Integer("Bids won", compute="_compute_counts", store=True)
    # Project fields carried onto the bid for grouping in reports.
    engineer_id = fields.Many2one(related="job_id.engineer_id", store=True)
    project_type_id = fields.Many2one(related="job_id.project_type_id", store=True)
    lead_source_id = fields.Many2one(related="job_id.lead_source_id", store=True)
    notes = fields.Text()

    def action_open_record(self):
        """Open the full record from a list embedded in its parent, rather than the edit dialog."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _twp_bs_touch(self, summary, note=False, next_date=False):
        """Record a contact: post it, close the open follow-ups, and schedule the next one.

        Every follow-up is a plain activity, so reminders and My Activities work as usual.
        """
        for quote in self:
            body = Markup("%s<br/>%s") % (summary, note) if note else summary
            open_activities = quote.activity_ids
            if open_activities:
                open_activities.action_feedback(feedback=note or summary)
            quote.message_post(body=body)
            if next_date:
                quote.activity_schedule(
                    "mail.mail_activity_data_todo", date_deadline=next_date,
                    summary=_("Follow up"), user_id=(quote.user_id or self.env.user).id)

    def action_twp_bs_log_touch(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Log a touch"),
            "res_model": "twp.bid.spec.touch",
            "view_mode": "form",
            "target": "new",
            "context": {"default_quote_id": self.id},
        }

    @api.depends("partner_id.name", "job_id.display_name")
    def _compute_display_name(self):
        for quote in self:
            quote.display_name = f"{quote.partner_id.name or ''} - {quote.job_id.display_name or ''}"

    @api.depends("amount", "margin")
    def _compute_gross_profit(self):
        for quote in self:
            quote.gross_profit = quote.amount * quote.margin

    @api.depends("quote_date", "result")
    def _compute_counts(self):
        for quote in self:
            quote.quotes_sent = int(bool(quote.quote_date))
            quote.quotes_decided = int(quote.result in DECIDED_RESULTS)
            quote.quotes_won = int(quote.result == "won")

    @api.depends("quote_date", "first_contact_date")
    def _compute_reporting_date(self):
        for quote in self:
            quote.reporting_date = quote.quote_date or quote.first_contact_date

    @api.depends("result_override", "quote_date", "partner_id", "lead_id.twp_bs_status",
                 "job_id.awarded_partner_id", "job_id.bought_through_partner_id", "job_id.installed_partner_id",
                 "job_id.installed_partner_id.twp_bs_we_represent")
    def _compute_result(self):
        # The override first, then each outcome in turn.
        for quote in self:
            job = quote.job_id
            status = quote.lead_id.twp_bs_status
            if quote.result_override:
                result = quote.result_override
            elif not quote.quote_date:
                result = "not_quoted"
            elif status == "cancelled":
                result = "project_dead"
            elif status != "awarded":
                result = "pending"
            elif not job.awarded_partner_id:
                result = "awarded_update"
            # A contractor buying through a distributor makes the distributor's bid the win.
            elif quote.partner_id != (job.bought_through_partner_id or job.awarded_partner_id):
                result = "lost_contractor"
            elif not job.installed_partner_id:
                result = "awarded_update"
            elif job.installed_partner_id.twp_bs_we_represent:
                result = "won"
            else:
                result = "lost_mfr"
            quote.result = result
