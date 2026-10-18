from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from .twp_bid_spec_quote import QUOTED_AS


class TwpBidSpecDashboard(models.TransientModel):
    """Every Bid / Spec figure for a reporting window the user picks.

    Jobs and bids fall in the window by reporting date (bid sent, else first contact), and
    projects by bid date. Nothing is stored; the page is recalculated whenever the window changes.
    """
    _name = "twp.bid.spec.dashboard"
    _description = 'Bid / Spec dashboard'

    date_from = fields.Date('From', required=True, default=lambda self: self._default_dates()[0])
    date_to = fields.Date('To', required=True, default=lambda self: self._default_dates()[1])
    body = fields.Html(compute='_compute_body', sanitize=False)

    def _default_dates(self):
        today = fields.Date.context_today(self)
        return today.replace(month=1, day=1), today.replace(month=12, day=31)

    def _compute_display_name(self):
        for dash in self:
            dash.display_name = _('Bid / Spec dashboard')

    @api.depends('date_from', 'date_to')
    def _compute_body(self):
        for dash in self:
            if not dash.date_from or not dash.date_to:
                dash.body = False
                continue
            dash.body = self.env['ir.qweb']._render('twp_bid_spec.dashboard_body', dash._twp_bs_page())

    # The numbers. Kept apart from the page so tests can check them.

    def _twp_bs_tracked_projects(self):
        """Bid / Spec projects that were not passed at review: open, or lost as cancelled / postponed."""
        cancelled = self.env['res.company'].search([]).twp_bs_cancelled_reason_id
        return self.env['crm.lead'].with_context(active_test=False).search([
            ('type', '=', 'opportunity'),
            ('twp_bs_is_bid_spec', '=', True),
            '|', ('active', '=', True), ('lost_reason_id', 'in', cancelled.ids),
        ])

    def _twp_bs_window(self, records, field):
        return records.filtered(lambda r: r[field] and self.date_from <= r[field] <= self.date_to)

    @staticmethod
    def _twp_bs_job_stats(jobs):
        decided = sum(jobs.mapped('jobs_decided'))
        won = sum(jobs.mapped('jobs_won'))
        return {
            'quoted': sum(jobs.mapped('jobs_quoted')),
            'decided': decided,
            'won': won,
            'rate': won / decided if decided else None,
            'quoted_amount': sum(jobs.mapped('quoted_amount')),
            'won_amount': sum(jobs.mapped('won_amount')),
            'won_gp': sum(jobs.mapped('won_gross_profit')),
        }

    @staticmethod
    def _twp_bs_quote_stats(quotes):
        decided = sum(quotes.mapped('quotes_decided'))
        won = sum(quotes.mapped('quotes_won'))
        return {
            'sent': sum(quotes.mapped('quotes_sent')),
            'decided': decided,
            'won': won,
            'rate': won / decided if decided else None,
        }

    def _twp_bs_figures(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        due_window = self.env.company.twp_bs_due_window_days
        all_jobs = self.env['twp.bid.spec.job'].search([])
        all_quotes = self.env['twp.bid.spec.quote'].search([])
        jobs = self._twp_bs_window(all_jobs, 'reporting_date')
        quotes = self._twp_bs_window(all_quotes, 'reporting_date')
        projects = self._twp_bs_tracked_projects()
        window_projects = self._twp_bs_window(projects, 'twp_bs_bid_date')
        bidding = projects.filtered(lambda p: p.active and p.twp_bs_status == 'bidding')
        Followup = self.env['twp.bid.spec.followup']

        key = self._twp_bs_job_stats(jobs)
        pending = sum(all_jobs.mapped('pending_amount'))
        key.update({
            'projects': len(window_projects),
            'pending': pending,
            'expected': pending * key['rate'] if key['rate'] is not None else None,
            'overdue': Followup.search_count([('date_deadline', '<', today)]),
            'due_week': Followup.search_count([
                ('date_deadline', '>=', today), ('date_deadline', '<=', today + timedelta(days=7))]),
            'no_contractors': len(bidding.filtered(lambda p: not p.twp_bs_quote_count)),
            'bids_due': len(bidding.filtered(
                lambda p: p.twp_bs_bid_date and today <= p.twp_bs_bid_date <= today + timedelta(days=due_window))),
            'due_window': due_window,
            'rate_proactive': self._twp_bs_quote_stats(
                quotes.filtered(lambda q: q.source_kind == 'proactive'))['rate'],
            'rate_inbound': self._twp_bs_quote_stats(
                quotes.filtered(lambda q: q.source_kind == 'inbound'))['rate'],
        })

        funnel = [
            ('tracked', len(window_projects)),
            ('contacted', len(window_projects.filtered('twp_bs_quote_count'))),
            ('quoted', len(window_projects.filtered('twp_bs_quotes_sent_count'))),
            ('decided', len(window_projects.filtered('twp_bs_quotes_decided_count'))),
            ('won', len(window_projects.filtered('twp_bs_quotes_won_count'))),
        ]

        months = []
        start = self.date_from.replace(day=1)
        for i in range(12):
            month_start = start + relativedelta(months=i)
            month_end = month_start + relativedelta(months=1)
            month_jobs = all_jobs.filtered(
                lambda j: j.reporting_date and month_start <= j.reporting_date < month_end)
            months.append({
                'month': month_start,
                'quotes_sent': len(all_quotes.filtered(
                    lambda q: q.quote_date and month_start <= q.quote_date < month_end)),
                'jobs_quoted': sum(month_jobs.mapped('jobs_quoted')),
                'jobs_won': sum(month_jobs.mapped('jobs_won')),
                'won_amount': sum(month_jobs.mapped('won_amount')),
            })

        sources = self.env['utm.source'].search([
            '|', ('twp_bs_annual_cost', '>', 0), ('id', 'in', all_jobs.lead_source_id.ids)])
        quote_sources = [('proactive', _('All proactive outreach'), lambda q: q.source_kind == 'proactive'),
                         ('inbound', _('All inbound requests'), lambda q: q.source_kind == 'inbound')]
        quote_sources += [(source.id, source.name, lambda q, s=source: q.source_id == s)
                          for source in self.env['twp.bid.spec.source'].search([])]

        return {
            'key': key,
            'funnel': funnel,
            'months': months,
            'product_lines': [
                (line.name, self._twp_bs_job_stats(jobs.filtered(lambda j, l=line: j.product_line_id == l)))
                for line in self.env['twp.bid.spec.product.line'].search([])],
            'bod': [
                (_('Our equipment is the basis of design'), self._twp_bs_job_stats(jobs.filtered('bod_is_ours'))),
                (_('A competitor is the basis of design'), self._twp_bs_job_stats(
                    jobs.filtered(lambda j: j.bod_partner_id and not j.bod_is_ours))),
            ],
            'quoted_as': [
                (label, self._twp_bs_job_stats(jobs.filtered(lambda j, c=code: j.quoted_as == c)))
                for code, label in QUOTED_AS],
            'project_types': [
                (ptype.name, self._twp_bs_job_stats(jobs.filtered(lambda j, t=ptype: j.project_type_id == t)))
                for ptype in self.env['twp.bid.spec.project.type'].search([])],
            'lead_services': [
                (source.name, self._twp_bs_job_stats(jobs.filtered(lambda j, s=source: j.lead_source_id == s)),
                 source.twp_bs_annual_cost)
                for source in sources],
            'quote_sources': [
                (label, self._twp_bs_quote_stats(quotes.filtered(test))) for _code, label, test in quote_sources],
            'team': [
                (user.name, self._twp_bs_quote_stats(quotes.filtered(lambda q, u=user: q.user_id == u)))
                for user in quotes.user_id.sorted('name')],
        }

    # The page.

    def _twp_bs_page(self):
        figures = self._twp_bs_figures()
        currency = self.env.company.currency_id
        key = figures['key']
        # Translated here, where the lookup can find the user's language; the helpers below cannot.
        na = _('n/a')

        def money(value):
            if value is None:
                return na
            amount = f'{value:,.0f}'
            return f'{currency.symbol}{amount}' if currency.position == 'before' else f'{amount} {currency.symbol}'

        def pct(value):
            return na if value is None else f'{value:.0%}'

        def job_row(label, stats):
            return [label, stats['quoted'], stats['decided'], stats['won'], pct(stats['rate']),
                    money(stats['quoted_amount']), money(stats['won_amount']), money(stats['won_gp'])]

        def quote_row(label, stats):
            return [label, stats['sent'], stats['decided'], stats['won'], pct(stats['rate'])]

        job_columns = [_('Jobs bid'), _('Jobs decided'), _('Jobs won'), _('Job win rate'),
                       _('Bid $ (each job once)'), _('Won $'), _('Won GP $')]
        quote_columns = [_('Bids sent'), _('Decided'), _('Won'), _('Bid win rate')]
        tracked = figures['funnel'][0][1]
        funnel_meaning = {
            'tracked': (_('Tracked'), _('Bid / Spec projects with a bid date in the window, not passed at review')),
            'contacted': (_('Contacted'), _('At least one contractor line has been started')),
            'quoted': (_('Bid'), _('A bid was sent to at least one contractor')),
            'decided': (_('Decided'), _("Awarded or lost after we bid (excludes cancelled and 'Awarded - Update')")),
            'won': (_('Won'), _('We supplied at least one product line on the project')),
        }

        lead_service_rows = []
        for name, stats, cost in figures['lead_services']:
            ratio = f"{stats['won_gp'] / cost:.1f}x" if cost else ''
            lead_service_rows.append(job_row(name, stats) + [money(cost) if cost else '', ratio])

        cards = [
            (_('Projects tracked (bid date in window)'), key['projects']),
            (_('Jobs bid'), key['quoted']),
            (_('Jobs decided (won or lost)'), key['decided']),
            (_('Jobs won'), key['won']),
            (_('Job win rate'), pct(key['rate'])),
            (_('Bid $ (each job counted once)'), money(key['quoted_amount'])),
            (_('Won revenue $'), money(key['won_amount'])),
            (_('Won gross profit $'), money(key['won_gp'])),
            (_('Pending pipeline $ (all open jobs)'), money(key['pending'])),
            (_('Expected value at current win rate'), money(key['expected'])),
            (_('Follow-ups overdue'), key['overdue']),
            (_('Follow-ups due next 7 days'), key['due_week']),
            (_('Bidding - no contractors contacted'), key['no_contractors']),
            (_('Bids due in next %s days', key['due_window']), key['bids_due']),
            (_('Win rate - proactive bids'), pct(key['rate_proactive'])),
            (_('Win rate - inbound bids'), pct(key['rate_inbound'])),
        ]
        tables = [
            {
                'title': _('Funnel - projects with a bid date in the window'),
                'columns': [_('Stage'), _('Projects'), _('% of tracked'), _('What it means')],
                'numeric': {1, 2},
                'rows': [[funnel_meaning[stage][0], count, pct(count / tracked) if tracked else '',
                          funnel_meaning[stage][1]] for stage, count in figures['funnel']],
            },
            {
                'title': _("Monthly trend - 12 months starting with the 'from' month"),
                'columns': [_('Month'), _('Bids sent (lines)'), _('Jobs bid'), _('Jobs won'), _('Won $')],
                'rows': [[m['month'].strftime('%b %Y'), m['quotes_sent'], m['jobs_quoted'], m['jobs_won'],
                          money(m['won_amount'])] for m in figures['months']],
            },
            {
                'title': _('Results by product line - a job is one project and one product line'),
                'columns': [_('Product line')] + job_columns,
                'rows': [job_row(*row) for row in figures['product_lines']],
            },
            {
                'title': _("Does basis of design matter? Are we spec'd in, or trying to get in?"),
                'columns': [_('Basis of design')] + job_columns,
                'rows': [job_row(*row) for row in figures['bod']],
            },
            {
                'title': _('How we bid it'),
                'columns': [_('Bid as')] + job_columns,
                'rows': [job_row(*row) for row in figures['quoted_as']],
            },
            {
                'title': _('Results by project type'),
                'columns': [_('Project type')] + job_columns,
                'rows': [job_row(*row) for row in figures['project_types']],
            },
            {
                'title': _('Lead service performance - is each subscription paying for itself?'),
                'columns': [_('Lead service')] + job_columns + [_('Annual cost'), _('Won GP / cost')],
                'rows': lead_service_rows,
            },
            {
                'title': _('Outreach effectiveness by bid source - per contractor bid'),
                'columns': [_('Bid source')] + quote_columns,
                'rows': [quote_row(*row) for row in figures['quote_sources']],
            },
            {
                'title': _('Team activity - per contractor bid'),
                'columns': [_('Bid by')] + quote_columns,
                'rows': [quote_row(*row) for row in figures['team']],
            },
        ]
        # Every column but the label is a figure, and figures sit right-aligned.
        for table in tables:
            table.setdefault('numeric', set(range(1, len(table['columns']))))
        # The two trend charts, as bars sized against the largest value in each chart.
        funnel_top = max([count for _stage, count in figures['funnel']] + [1])
        month_top = max([max(m['jobs_quoted'], m['jobs_won']) for m in figures['months']] + [1])
        charts = {
            'funnel': [(funnel_meaning[stage][0], count, round(100 * count / funnel_top))
                       for stage, count in figures['funnel']],
            'months': [(m['month'].strftime('%b'), m['jobs_quoted'], m['jobs_won'],
                        round(100 * m['jobs_quoted'] / month_top), round(100 * m['jobs_won'] / month_top))
                       for m in figures['months']],
        }
        return {'cards': cards, 'charts': charts, 'tables': tables}

    # Drill down from the window into the records behind it.

    def _twp_bs_open(self, model, name, view_mode):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': view_mode,
            'domain': [('reporting_date', '>=', self.date_from), ('reporting_date', '<=', self.date_to)],
        }

    def action_open_jobs(self):
        return self._twp_bs_open('twp.bid.spec.job', _('Jobs in window'), 'pivot,graph,list,form')

    def action_open_quotes(self):
        return self._twp_bs_open('twp.bid.spec.quote', _('Bids in window'), 'pivot,graph,list,form')
