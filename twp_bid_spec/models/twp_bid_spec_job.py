from odoo import api, fields, models

from .twp_bid_spec_quote import DECIDED_RESULTS, QUOTED_AS


class TwpBidSpecJob(models.Model):
    """One project and one product line: what is won or lost."""

    _name = "twp.bid.spec.job"
    _description = "Bid job"
    _inherit = ["mail.thread"]
    _order = "lead_id, sequence, id"

    lead_id = fields.Many2one("crm.lead", string="Project", required=True, index=True, ondelete="cascade")
    product_line_id = fields.Many2one("twp.bid.spec.product.line", string="Product line", required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related="lead_id.company_id", store=True)
    # Stored: Odoo only adds up money fields in pivots and graphs when their currency is stored.
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id", store=True)
    project_status = fields.Selection(related="lead_id.twp_bs_status", string="Bid status")
    engineer_id = fields.Many2one(related="lead_id.twp_bs_engineer_id", store=True)
    project_type_id = fields.Many2one(related="lead_id.twp_bs_project_type_id", store=True)
    lead_source_id = fields.Many2one(related="lead_id.source_id", string="Lead service", store=True)

    bod_partner_id = fields.Many2one("res.partner", string="Basis of design mfr", tracking=True)
    bod_model = fields.Char("BOD model")
    bod_is_ours = fields.Boolean(
        "Our equipment is BOD", compute="_compute_bod_is_ours", store=True,
        help="The basis-of-design manufacturer is one we represent.")
    or_equal = fields.Char("Or-equal wording")
    awarded_partner_id = fields.Many2one("res.partner", string="Awarded to", tracking=True)
    bought_through_partner_id = fields.Many2one(
        "res.partner", string="Bought through", tracking=True,
        help="The distributor the winning contractor buys the equipment through. Its bid is the win.")
    installed_partner_id = fields.Many2one("res.partner", string="Installed mfr", tracking=True)

    quote_ids = fields.One2many("twp.bid.spec.quote", "job_id", string="Bids")
    quote_count = fields.Integer("Number of bids", compute="_compute_figures", store=True)
    # Stored so reports can group and sum them.
    reporting_date = fields.Date("Reporting date", compute="_compute_figures", store=True)
    is_quoted = fields.Boolean("Bid sent", compute="_compute_figures", store=True)
    is_decided = fields.Boolean("Decided", compute="_compute_figures", store=True)
    is_won = fields.Boolean("Won", compute="_compute_figures", store=True)
    quoted_amount = fields.Monetary("Bid $", compute="_compute_figures", store=True)
    won_amount = fields.Monetary("Won $", compute="_compute_figures", store=True)
    won_gross_profit = fields.Monetary("Won GP", compute="_compute_figures", store=True)
    pending_amount = fields.Monetary("Pending $", compute="_compute_figures", store=True)
    # The same flags as 1 or 0, so a pivot can add them up.
    jobs_quoted = fields.Integer("Jobs bid", compute="_compute_figures", store=True)
    jobs_decided = fields.Integer("Jobs decided", compute="_compute_figures", store=True)
    jobs_won = fields.Integer("Jobs won", compute="_compute_figures", store=True)
    # A job is segmented by its first bid's Bid as.
    quoted_as = fields.Selection(QUOTED_AS, string="Bid as", compute="_compute_figures", store=True)

    _job_unique = models.Constraint(
        "UNIQUE(lead_id, product_line_id)", "A project has only one job per product line.")

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

    @api.depends("lead_id.name", "product_line_id.name")
    def _compute_display_name(self):
        for job in self:
            job.display_name = f"{job.lead_id.name or ''} - {job.product_line_id.name or ''}"

    @api.depends("company_id.currency_id")
    def _compute_currency_id(self):
        for job in self:
            job.currency_id = job.company_id.currency_id or self.env.company.currency_id

    @api.depends("bod_partner_id.twp_bs_we_represent")
    def _compute_bod_is_ours(self):
        for job in self:
            job.bod_is_ours = job.bod_partner_id.twp_bs_we_represent

    @api.depends("quote_ids.result", "quote_ids.quote_date", "quote_ids.first_contact_date",
                 "quote_ids.quoted_as", "quote_ids.amount", "quote_ids.gross_profit", "lead_id.twp_bs_status")
    def _compute_figures(self):
        for job in self:
            quotes = job.quote_ids
            results = quotes.mapped("result")
            won = quotes.filtered(lambda q: q.result == "won")
            amounts = [a for a in quotes.mapped("amount") if a > 0]
            job.quote_count = len(quotes)
            # A job reports on its first bid's date: bid sent, else first contact.
            job.reporting_date = quotes[:1].reporting_date
            job.quoted_as = quotes[:1].quoted_as
            job.is_quoted = any(quotes.mapped("quote_date"))
            job.is_won = bool(won)
            # Decided: something won, or something lost with no award still waiting on an update.
            job.is_decided = bool(won) or (
                any(r in DECIDED_RESULTS for r in results) and "awarded_update" not in results)
            # Each job counted once: the average of its bids, not their sum.
            job.quoted_amount = sum(amounts) / len(amounts) if job.is_quoted and amounts else 0.0
            job.won_amount = sum(won.mapped("amount"))
            job.won_gross_profit = sum(won.mapped("gross_profit"))
            job.pending_amount = job.quoted_amount if (
                job.is_quoted and not job.is_decided and job.lead_id.twp_bs_status != "cancelled") else 0.0
            job.jobs_quoted = int(job.is_quoted)
            job.jobs_decided = int(job.is_decided)
            job.jobs_won = int(job.is_won)
