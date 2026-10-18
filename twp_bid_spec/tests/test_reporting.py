from datetime import date

from lxml import etree

from odoo.tests import tagged

from .common import TwpBidSpecCase


@tagged('post_install', '-at_install')
class TestReporting(TwpBidSpecCase):
    """The dashboard and the contractor and engineer scorecards.

    Everything is dated 2025 so the window holds only this test's records, whatever else the
    database carries.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        Role = cls.env['twp.bid.spec.partner.role']
        engineer = Role.create({'name': 'TWP Engineer', 'kind': 'engineer'})
        mechanical = Role.create({'name': 'TWP Mechanical contractor', 'kind': 'contractor'})
        cls.engineer = Partner.create({'name': 'TWP Engineering Group', 'twp_bs_role_ids': [engineer.id]})
        cls.contractor_a.twp_bs_role_ids = mechanical
        cls.idle = Partner.create({'name': 'TWP C Never Quoted', 'twp_bs_role_ids': [mechanical.id]})
        cls.planhub = cls.env['utm.source'].create({'name': 'TWP PlanHub'})
        cls.warehouse = cls.env['twp.bid.spec.project.type'].create({'name': 'TWP Warehouse'})
        Source = cls.env['twp.bid.spec.source']
        cls.bidder_list = Source.create({'name': 'TWP Proactive - Bidder List', 'kind': 'proactive'})
        cls.relationship = Source.create({'name': 'TWP Proactive - Relationship', 'kind': 'proactive'})
        cls.inbound = Source.create({'name': 'TWP Inbound', 'kind': 'inbound'})
        Job = cls.env['twp.bid.spec.job']
        Quote = cls.env['twp.bid.spec.quote']

        # Won: two contractors quoted, A was awarded and installed our equipment.
        cls.won_project = cls._project('Won project', date(2025, 3, 1))
        cls.won_job = Job.create({
            'lead_id': cls.won_project.id, 'product_line_id': cls.infrared.id, 'bod_partner_id': cls.ours.id})
        cls.won_quote = Quote.create({
            'job_id': cls.won_job.id, 'partner_id': cls.contractor_a.id, 'source_id': cls.bidder_list.id,
            'quoted_as': 'bod', 'first_contact_date': date(2025, 3, 5), 'quote_date': date(2025, 3, 10),
            'amount': 40000, 'margin': 0.25})
        cls.lost_quote = Quote.create({
            'job_id': cls.won_job.id, 'partner_id': cls.contractor_b.id, 'source_id': cls.inbound.id,
            'quoted_as': 'approved_equal', 'quote_date': date(2025, 3, 12), 'amount': 50000, 'margin': 0.2})
        cls.won_project.stage_id = cls.stage_awarded
        cls.won_job.write({'awarded_partner_id': cls.contractor_a.id, 'installed_partner_id': cls.ours.id})

        # Open: one pending quote, so the job is quoted and still in the pipeline.
        cls.open_project = cls._project('Open project', date(2025, 4, 15))
        cls.open_job = Job.create({'lead_id': cls.open_project.id, 'product_line_id': cls.hvls.id})
        cls.open_quote = Quote.create({
            'job_id': cls.open_job.id, 'partner_id': cls.contractor_a.id, 'source_id': cls.relationship.id,
            'quote_date': date(2025, 4, 1), 'last_contact_date': date(2025, 4, 8), 'amount': 20000})

        # Passed at review: never tracked, so it counts nowhere.
        cls.passed_project = cls._project('Passed project', date(2025, 5, 1))
        cls.passed_project.action_set_lost(lost_reason_id=cls.no_scope.id)

        cls.dashboard = cls.env['twp.bid.spec.dashboard'].create({
            'date_from': date(2025, 1, 1), 'date_to': date(2025, 12, 31)})

    @classmethod
    def _project(cls, name, bid_date):
        return super()._project(name, twp_bs_bid_date=bid_date, twp_bs_engineer_id=cls.engineer.id,
                                source_id=cls.planhub.id, twp_bs_project_type_id=cls.warehouse.id)

    def test_job_and_quote_counters(self):
        self.assertEqual((self.won_job.jobs_quoted, self.won_job.jobs_decided, self.won_job.jobs_won), (1, 1, 1))
        self.assertEqual(self.won_job.quoted_as, 'bod', "A job takes its first line's Quoted As")
        self.assertEqual((self.open_job.jobs_quoted, self.open_job.jobs_decided), (1, 0))
        self.assertEqual((self.lost_quote.quotes_sent, self.lost_quote.quotes_decided, self.lost_quote.quotes_won),
                         (1, 1, 0))
        self.assertEqual(self.won_quote.source_kind, 'proactive')
        self.assertEqual(self.lost_quote.source_kind, 'inbound')
        self.assertEqual(self.won_quote.lead_source_id, self.planhub)

    def test_key_results(self):
        key = self.dashboard._twp_bs_figures()['key']
        self.assertEqual(key['projects'], 2, "The passed project is not tracked")
        self.assertEqual((key['quoted'], key['decided'], key['won']), (2, 1, 1))
        self.assertEqual(key['rate'], 1.0)
        # Each job counted once: the won job averages 40,000 and 50,000.
        self.assertEqual(key['quoted_amount'], 45000 + 20000)
        self.assertEqual(key['won_amount'], 40000)
        self.assertEqual(key['won_gp'], 10000)
        self.assertEqual(self.open_job.pending_amount, 20000)
        self.assertEqual(key['expected'], key['pending'] * key['rate'])
        self.assertEqual(key['rate_proactive'], 1.0, "Proactive: one won, the pending line undecided")
        self.assertEqual(key['rate_inbound'], 0.0)

    def test_funnel_and_months(self):
        figures = self.dashboard._twp_bs_figures()
        self.assertEqual(dict(figures['funnel']), {
            'tracked': 2, 'contacted': 2, 'quoted': 2, 'decided': 1, 'won': 1})
        march, april = figures['months'][2], figures['months'][3]
        self.assertEqual((march['quotes_sent'], march['jobs_quoted'], march['jobs_won'], march['won_amount']),
                         (2, 1, 1, 40000))
        self.assertEqual((april['quotes_sent'], april['jobs_quoted'], april['jobs_won']), (1, 1, 0))

    def test_segments(self):
        figures = self.dashboard._twp_bs_figures()
        lines = dict(figures['product_lines'])
        self.assertEqual((lines[self.infrared.name]['won'], lines[self.hvls.name]['quoted']), (1, 1))
        bod = dict(figures['bod'])
        self.assertEqual(bod['Our equipment is the basis of design']['won'], 1)
        self.assertEqual(bod['A competitor is the basis of design']['quoted'], 0)
        services = {name: (stats, cost) for name, stats, cost in figures['lead_services']}
        self.assertEqual(services[self.planhub.name][0]['quoted'], 2)
        sources = dict(figures['quote_sources'])
        self.assertEqual((sources['All proactive outreach']['sent'], sources['All proactive outreach']['won']), (2, 1))
        self.assertEqual(sources['All inbound requests']['decided'], 1)
        team = dict(figures['team'])
        self.assertEqual(team[self.env.user.name]['sent'], 3)

    def test_contractor_scorecard(self):
        self.env.flush_all()
        rows = self.env['twp.bid.spec.contractor.scorecard'].search([
            ('partner_id', 'in', (self.contractor_a | self.contractor_b | self.idle).ids)])
        card = {row.partner_id: row for row in rows}
        a, b = card[self.contractor_a], card[self.contractor_b]
        self.assertEqual((a.lines_tracked, a.quotes_sent, a.quotes_decided, a.quotes_won), (2, 2, 1, 1))
        self.assertEqual((a.win_rate, a.won_amount, a.jobs_awarded), (1.0, 40000, 1))
        self.assertEqual(a.last_activity, date(2025, 4, 8))
        self.assertEqual((b.quotes_decided, b.quotes_won, b.win_rate), (1, 0, 0.0))
        self.assertEqual(card[self.idle].lines_tracked, 0, "A contractor is listed before any bid")

    def test_engineer_scorecard(self):
        self.env.flush_all()
        row = self.env['twp.bid.spec.engineer.scorecard'].search([('partner_id', '=', self.engineer.id)])
        self.assertEqual(row.projects, 2, "The passed project is not counted")
        self.assertEqual((row.jobs_tracked, row.jobs_bod_ours, row.bod_rate), (2, 1, 0.5))
        self.assertEqual((row.jobs_decided, row.jobs_won, row.win_rate, row.won_amount), (1, 1, 1.0, 40000))

    def test_dashboard_page_renders(self):
        body = str(self.dashboard.body)
        self.assertIn('Jobs bid', body)
        self.assertIn('$40,000', body)
        self.assertIn('Mar 2025', body)
        self.assertIn('Jobs bid vs. won by month', body)
        self.assertIn('Funnel - projects in window', body)
        action = self.dashboard.action_open_jobs()
        self.assertEqual(self.env['twp.bid.spec.job'].search(action['domain']), self.won_job | self.open_job)

    def test_every_measure_can_be_added_up(self):
        """The browser refuses a pivot or graph whose measure has no aggregator, before loading any data.

        Money fields only get one when their currency field is stored.
        """
        for model in ('twp.bid.spec.job', 'twp.bid.spec.quote'):
            for view_type in ('pivot', 'graph'):
                arch = self.env[model].get_view(view_type=view_type)['arch']
                measures = etree.fromstring(arch).xpath("//field[@type='measure']/@name")
                info = self.env[model].fields_get(measures, ['aggregator'])
                for name in measures:
                    self.assertTrue(info[name].get('aggregator'), f"{model}.{name} has no aggregator")
            # The list's default measure options include every summable field, so check those too.
            money = [name for name, field in self.env[model]._fields.items() if field.type == 'monetary' and field.store]
            for name, attrs in self.env[model].fields_get(money, ['aggregator']).items():
                self.assertTrue(attrs.get('aggregator'), f"{model}.{name} has no aggregator")
