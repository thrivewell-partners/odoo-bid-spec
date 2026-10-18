from odoo import _, fields, models, tools


class TwpBidSpecFollowup(models.Model):
    """The follow-up queue: every open follow-up on a bid or project still in play.

    A read-only view over activities. A bid drops out once it is decided, and a project once it is
    awarded or dead. Logging a touch closes the row's activity.
    """

    _name = "twp.bid.spec.followup"
    _description = "Follow-up queue"
    _auto = False
    _order = "date_deadline, id"

    activity_id = fields.Many2one("mail.activity", string="Activity record", readonly=True)
    date_deadline = fields.Date("Due", readonly=True)
    days_due = fields.Integer("Days (neg = overdue)", compute="_compute_days_due")
    user_id = fields.Many2one("res.users", string="Rep", readonly=True)
    summary = fields.Char("Activity", readonly=True)
    activity_type_id = fields.Many2one("mail.activity.type", readonly=True)
    quote_id = fields.Many2one("twp.bid.spec.quote", string="Bid", readonly=True)
    lead_id = fields.Many2one("crm.lead", string="Project", readonly=True)
    job_id = fields.Many2one("twp.bid.spec.job", string="Job", readonly=True)
    product_line_id = fields.Many2one("twp.bid.spec.product.line", string="Product line", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contractor", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    amount = fields.Monetary("Bid $", readonly=True)
    result = fields.Selection(related="quote_id.result")
    last_contact_date = fields.Date("Last activity", readonly=True)

    def _compute_days_due(self):
        today = fields.Date.context_today(self)
        for row in self:
            row.days_due = (row.date_deadline - today).days if row.date_deadline else 0

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT a.id,
                       a.id AS activity_id,
                       a.date_deadline,
                       a.user_id,
                       a.summary,
                       a.activity_type_id,
                       q.id AS quote_id,
                       COALESCE(q.lead_id, l.id) AS lead_id,
                       q.job_id,
                       q.product_line_id,
                       q.partner_id,
                       COALESCE(ql.company_id, l.company_id) AS company_id,
                       q.amount,
                       GREATEST(q.first_contact_date, q.quote_date, q.last_contact_date) AS last_contact_date
                  FROM mail_activity a
             LEFT JOIN twp_bid_spec_quote q ON a.res_model = 'twp.bid.spec.quote' AND q.id = a.res_id
             LEFT JOIN crm_lead ql ON ql.id = q.lead_id
             LEFT JOIN crm_lead l ON a.res_model = 'crm.lead' AND l.id = a.res_id
                 WHERE a.active
                   AND ((q.id IS NOT NULL
                         AND q.result IN ('not_quoted', 'pending')
                         AND ql.twp_bs_status IN ('bidding', 'opened'))
                     OR (l.id IS NOT NULL
                         AND l.active
                         AND l.twp_bs_status IN ('bidding', 'opened')))
            )
        """)

    def action_log_touch(self):
        self.ensure_one()
        return self.quote_id.action_twp_bs_log_touch()

    def action_open(self):
        self.ensure_one()
        record = self.quote_id or self.lead_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Follow-up"),
            "res_model": record._name,
            "res_id": record.id,
            "view_mode": "form",
            "target": "current",
        }
