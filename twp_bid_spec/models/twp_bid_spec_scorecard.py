from odoo import _, fields, models, tools

# A project counts as tracked unless it was passed at review: open, or lost as cancelled / postponed.
TRACKED_PROJECT_SQL = """
    l.type = 'opportunity'
    AND l.twp_bs_is_bid_spec
    AND (l.active OR l.lost_reason_id IN (SELECT twp_bs_cancelled_reason_id FROM res_company
                                           WHERE twp_bs_cancelled_reason_id IS NOT NULL))
"""


# A column, not a compute, so the scorecards' money columns can be totalled when grouped.
COMPANY_CURRENCY_SQL = "(SELECT currency_id FROM res_company ORDER BY id LIMIT 1)"


def _role_partners_sql(kind):
    return f"""
        SELECT rel.partner_id
          FROM twp_bs_partner_role_rel rel
          JOIN twp_bid_spec_partner_role r ON r.id = rel.role_id
         WHERE r.kind = '{kind}'
    """


class TwpBidSpecContractorScorecard(models.Model):
    """One row per contractor, all time.

    A contractor is listed once they carry a role of the Contractor kind, have had a bid, or were
    awarded a job.
    """
    _name = 'twp.bid.spec.contractor.scorecard'
    _description = 'Contractor scorecard'
    _auto = False
    _order = 'quotes_won desc, quotes_sent desc, partner_id'

    partner_id = fields.Many2one('res.partner', string='Contractor', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    lines_tracked = fields.Integer('Lines tracked', readonly=True)
    quotes_sent = fields.Integer('Bids sent', readonly=True)
    quotes_decided = fields.Integer('Decided', readonly=True)
    quotes_won = fields.Integer('Won', readonly=True)
    win_rate = fields.Float('Bid win rate', readonly=True, aggregator=False)
    won_amount = fields.Monetary('Won $', readonly=True)
    jobs_awarded = fields.Integer('Jobs awarded to them', readonly=True)
    last_activity = fields.Date('Last activity', readonly=True, aggregator='max')
    days_since_contact = fields.Integer('Days since contact', readonly=True, aggregator=False)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH q AS (
                    SELECT partner_id,
                           COUNT(*) AS lines_tracked,
                           COUNT(quote_date) AS quotes_sent,
                           SUM(quotes_decided) AS quotes_decided,
                           SUM(quotes_won) AS quotes_won,
                           SUM(CASE WHEN result = 'won' THEN amount ELSE 0 END) AS won_amount,
                           MAX(GREATEST(first_contact_date, quote_date, last_contact_date)) AS last_activity
                      FROM twp_bid_spec_quote
                  GROUP BY partner_id
                ), a AS (
                    SELECT awarded_partner_id AS partner_id, COUNT(*) AS jobs_awarded
                      FROM twp_bid_spec_job
                     WHERE awarded_partner_id IS NOT NULL
                  GROUP BY awarded_partner_id
                ), base AS (
                    SELECT partner_id FROM q
                     UNION SELECT partner_id FROM a
                     UNION {_role_partners_sql('contractor')}
                )
                SELECT b.partner_id AS id,
                       b.partner_id,
                       {COMPANY_CURRENCY_SQL} AS currency_id,
                       COALESCE(q.lines_tracked, 0) AS lines_tracked,
                       COALESCE(q.quotes_sent, 0) AS quotes_sent,
                       COALESCE(q.quotes_decided, 0) AS quotes_decided,
                       COALESCE(q.quotes_won, 0) AS quotes_won,
                       CASE WHEN q.quotes_decided > 0
                            THEN q.quotes_won::float / q.quotes_decided END AS win_rate,
                       COALESCE(q.won_amount, 0) AS won_amount,
                       COALESCE(a.jobs_awarded, 0) AS jobs_awarded,
                       q.last_activity,
                       CURRENT_DATE - q.last_activity AS days_since_contact
                  FROM base b
             LEFT JOIN q ON q.partner_id = b.partner_id
             LEFT JOIN a ON a.partner_id = b.partner_id
            )
        """)

    def action_open_quotes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bids - %s', self.partner_id.display_name),
            'res_model': 'twp.bid.spec.quote',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }


class TwpBidSpecEngineerScorecard(models.Model):
    """How often each engineering firm specifies our equipment, and how often we win their jobs.
    All time. A job counts once a contractor has been contacted on it.
    """
    _name = 'twp.bid.spec.engineer.scorecard'
    _description = 'Engineer scorecard'
    _auto = False
    _order = 'jobs_won desc, jobs_tracked desc, partner_id'

    partner_id = fields.Many2one('res.partner', string='Engineering firm', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    projects = fields.Integer('Projects', readonly=True)
    jobs_tracked = fields.Integer('Jobs tracked', readonly=True)
    jobs_bod_ours = fields.Integer('Jobs with our equipment as BOD', readonly=True)
    bod_rate = fields.Float('% BOD ours', readonly=True, aggregator=False)
    jobs_decided = fields.Integer('Jobs decided', readonly=True)
    jobs_won = fields.Integer('Jobs won', readonly=True)
    win_rate = fields.Float('Job win rate', readonly=True, aggregator=False)
    won_amount = fields.Monetary('Won $', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH p AS (
                    SELECT l.twp_bs_engineer_id AS partner_id, COUNT(*) AS projects
                      FROM crm_lead l
                     WHERE l.twp_bs_engineer_id IS NOT NULL AND {TRACKED_PROJECT_SQL}
                  GROUP BY l.twp_bs_engineer_id
                ), j AS (
                    SELECT engineer_id AS partner_id,
                           COUNT(*) AS jobs_tracked,
                           COUNT(*) FILTER (WHERE bod_is_ours) AS jobs_bod_ours,
                           SUM(jobs_decided) AS jobs_decided,
                           SUM(jobs_won) AS jobs_won,
                           SUM(won_amount) AS won_amount
                      FROM twp_bid_spec_job
                     WHERE engineer_id IS NOT NULL AND quote_count > 0
                  GROUP BY engineer_id
                ), base AS (
                    SELECT partner_id FROM p
                     UNION SELECT partner_id FROM j
                     UNION {_role_partners_sql('engineer')}
                )
                SELECT b.partner_id AS id,
                       b.partner_id,
                       {COMPANY_CURRENCY_SQL} AS currency_id,
                       COALESCE(p.projects, 0) AS projects,
                       COALESCE(j.jobs_tracked, 0) AS jobs_tracked,
                       COALESCE(j.jobs_bod_ours, 0) AS jobs_bod_ours,
                       CASE WHEN j.jobs_tracked > 0
                            THEN j.jobs_bod_ours::float / j.jobs_tracked END AS bod_rate,
                       COALESCE(j.jobs_decided, 0) AS jobs_decided,
                       COALESCE(j.jobs_won, 0) AS jobs_won,
                       CASE WHEN j.jobs_decided > 0
                            THEN j.jobs_won::float / j.jobs_decided END AS win_rate,
                       COALESCE(j.won_amount, 0) AS won_amount
                  FROM base b
             LEFT JOIN p ON p.partner_id = b.partner_id
             LEFT JOIN j ON j.partner_id = b.partner_id
            )
        """)

    def action_open_jobs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Jobs - %s', self.partner_id.display_name),
            'res_model': 'twp.bid.spec.job',
            'view_mode': 'list,form',
            'domain': [('engineer_id', '=', self.partner_id.id)],
        }
