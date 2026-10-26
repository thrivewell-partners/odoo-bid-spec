from datetime import date, timedelta

from odoo import fields
from odoo.tests import tagged

from .common import TwpBidSpecCase


@tagged('post_install', '-at_install')
class TestResult(TwpBidSpecCase):
    """RESULT and the job counting rules."""

    def _job(self, project, line=None):
        return self.env['twp.bid.spec.job'].create({
            'lead_id': project.id, 'product_line_id': (line or self.infrared).id})

    def _quote(self, job, contractor, **vals):
        return self.env['twp.bid.spec.quote'].create({'job_id': job.id, 'partner_id': contractor.id, **vals})

    def _award(self, project, job, contractor=None, installed=None):
        project.stage_id = self.stage_awarded
        job.write({
            'awarded_partner_id': contractor.id if contractor else False,
            'installed_partner_id': installed.id if installed else False,
        })

    # The seven outcomes, in the order RESULT tests them.

    def test_not_quoted(self):
        quote = self._quote(self._job(self._project()), self.contractor_a)
        self.assertEqual(quote.result, 'not_quoted')

    def test_project_dead(self):
        project = self._project()
        quote = self._quote(self._job(project), self.contractor_a, quote_date=date(2026, 9, 22))
        project.action_set_lost(lost_reason_id=self.cancelled.id)
        self.assertEqual(project.twp_bs_status, 'cancelled')
        self.assertEqual(quote.result, 'project_dead')

    def test_pending_until_awarded(self):
        project = self._project()
        quote = self._quote(self._job(project), self.contractor_a, quote_date=date(2026, 9, 22))
        self.assertEqual(quote.result, 'pending')
        project.stage_id = self.stage_opened
        self.assertEqual(project.twp_bs_status, 'opened')
        self.assertEqual(quote.result, 'pending')

    def test_awarded_no_contractor_needs_update(self):
        project = self._project()
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22))
        self._award(project, job)
        self.assertEqual(quote.result, 'awarded_update')

    def test_lost_other_contractor(self):
        project = self._project()
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22))
        self._award(project, job, contractor=self.contractor_b, installed=self.ours)
        self.assertEqual(quote.result, 'lost_contractor')

    def test_awarded_no_installed_mfr_needs_update(self):
        project = self._project()
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22))
        self._award(project, job, contractor=self.contractor_a)
        self.assertEqual(quote.result, 'awarded_update')

    def test_won(self):
        project = self._project()
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22))
        self._award(project, job, contractor=self.contractor_a, installed=self.ours)
        self.assertEqual(quote.result, 'won')

    def test_lost_other_mfr(self):
        project = self._project()
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22))
        self._award(project, job, contractor=self.contractor_a, installed=self.theirs)
        self.assertEqual(quote.result, 'lost_mfr')

    def test_override_comes_first(self):
        quote = self._quote(self._job(self._project()), self.contractor_a, result_override='won')
        self.assertEqual(quote.result, 'won')

    def test_representing_a_mfr_later_turns_the_job_won(self):
        project = self._project()
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22))
        self._award(project, job, contractor=self.contractor_a, installed=self.theirs)
        self.assertEqual(quote.result, 'lost_mfr')
        self.theirs.twp_bs_we_represent = True
        self.assertEqual(quote.result, 'won')

    # Job-level counting rules.

    def test_job_won_figures(self):
        project = self._project()
        job = self._job(project)
        won = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22), amount=48500, margin=0.24)
        self._quote(job, self.contractor_b, quote_date=date(2026, 9, 23), amount=51500, margin=0.20)
        self._award(project, job, contractor=self.contractor_a, installed=self.ours)
        self.assertEqual(won.gross_profit, 11640)
        self.assertTrue(job.is_quoted and job.is_decided and job.is_won)
        self.assertEqual(job.quoted_amount, 50000, 'the average of its quotes, counted once')
        self.assertEqual(job.won_amount, 48500)
        self.assertEqual(job.won_gross_profit, 11640)
        self.assertEqual(job.pending_amount, 0)

    def test_awarded_update_keeps_a_lost_job_undecided(self):
        # One quote lost to another contractor, the other awaiting an update: not decided yet.
        project = self._project()
        job = self._job(project)
        lost = self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22), amount=40000)
        update = self._quote(job, self.contractor_b, quote_date=date(2026, 9, 22), amount=42000)
        self._award(project, job, contractor=self.contractor_b)
        self.assertEqual(lost.result, 'lost_contractor')
        self.assertEqual(update.result, 'awarded_update')
        self.assertFalse(job.is_decided)
        self.assertEqual(project.twp_bs_quotes_decided_count, 0)
        self.assertEqual(job.pending_amount, 41000)
        job.installed_partner_id = self.theirs
        self.assertEqual(update.result, 'lost_mfr')
        self.assertTrue(job.is_decided)
        self.assertFalse(job.is_won)
        self.assertEqual(project.twp_bs_quotes_decided_count, 2)

    def test_dead_project_has_no_pending_dollars(self):
        project = self._project()
        job = self._job(project)
        self._quote(job, self.contractor_a, quote_date=date(2026, 9, 22), amount=40000)
        self.assertEqual(job.pending_amount, 40000)
        project.action_set_lost(lost_reason_id=self.cancelled.id)
        self.assertEqual(job.pending_amount, 0)
        self.assertFalse(job.is_decided, 'Project Dead is not a loss')

    def test_job_reports_on_its_first_line(self):
        project = self._project()
        job = self._job(project)
        self._quote(job, self.contractor_a, first_contact_date=date(2026, 9, 19))
        self._quote(job, self.contractor_b, first_contact_date=date(2026, 9, 1), quote_date=date(2026, 9, 2))
        self.assertEqual(job.reporting_date, date(2026, 9, 19))

    def test_one_job_per_product_line(self):
        project = self._project()
        self._job(project)
        with self.assertRaises(Exception), self.cr.savepoint():
            self._job(project)
        self._job(project, self.hvls)
        self.assertEqual(project.twp_bs_job_count, 2)

    def test_needs_attention(self):
        project = self._project()
        project.twp_bs_bid_date = fields.Date.context_today(project) + timedelta(days=5)
        self.assertEqual(project.twp_needs_attention, 'No contractors contacted')
        job = self._job(project)
        quote = self._quote(job, self.contractor_a, first_contact_date=date(2026, 9, 19))
        project.invalidate_recordset(['twp_needs_attention'])
        self.assertEqual(project.twp_needs_attention, 'Bid within 7 days - no bid sent')
        self.env.company.twp_bs_warning_days = 3
        project.invalidate_recordset(['twp_needs_attention'])
        self.assertFalse(project.twp_needs_attention, "Five days out is outside a three-day warning")
        self.env.company.twp_bs_warning_days = 7
        quote.quote_date = date(2026, 9, 22)
        project.invalidate_recordset(['twp_needs_attention'])
        self.assertFalse(project.twp_needs_attention)

    def test_template_example(self):
        """Two bids on one job, one sent and one not yet, with the figures each should show."""
        project = self._project('EXAMPLE - Lincoln Distribution Warehouse')
        project.twp_bs_bid_date = date(2026, 10, 15)
        job = self._job(project)
        job.write({'bod_partner_id': self.ours.id, 'bod_model': 'IR-200'})
        line_1 = self._quote(
            job, self.contractor_a, source_id=self.env.ref('twp_bid_spec.source_proactive_bidder').id, quoted_as='bod', model_quoted='IR-200',
            first_contact_date=date(2026, 9, 19), quote_date=date(2026, 9, 22),
            last_contact_date=date(2026, 9, 22), amount=48500, margin=0.24)
        line_2 = self._quote(
            job, self.contractor_b, source_id=self.env.ref('twp_bid_spec.source_proactive_bidder').id, quoted_as='bod',
            first_contact_date=date(2026, 9, 19), last_contact_date=date(2026, 9, 19))
        self.assertTrue(job.bod_is_ours)
        self.assertEqual(line_1.gross_profit, 11640)
        self.assertEqual(line_1.result, 'pending')
        self.assertEqual(line_2.result, 'not_quoted')
        self.assertEqual(job.reporting_date, date(2026, 9, 22))
        self.assertEqual((job.is_quoted, job.is_decided, job.is_won), (True, False, False))
        self.assertEqual(job.quoted_amount, 48500)
        self.assertEqual(job.won_amount, 0)
        self.assertEqual(job.pending_amount, 48500)
        self.assertEqual(
            (project.twp_bs_quote_count, project.twp_bs_quotes_sent_count, project.twp_bs_quotes_won_count,
             project.twp_bs_quotes_decided_count),
            (2, 1, 0, 0))

    def test_open_record_from_parent_list(self):
        job = self._job(self._project())
        quote = self._quote(job, self.contractor_a)
        for record in (job, quote):
            action = record.action_open_record()
            self.assertEqual((action['res_model'], action['res_id'], action['view_mode']),
                             (record._name, record.id, 'form'))
