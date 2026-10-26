from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import TwpBidSpecCase


@tagged('post_install', '-at_install')
class TestWorkflow(TwpBidSpecCase):
    """The dialogs that move a project from review to award, and the follow-up queue."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parked = cls.env['crm.team'].create({'name': 'TWP Future leads'})
        cls.stage_parked = cls.env['crm.stage'].create({
            'name': 'TWP Parked', 'team_ids': [Command.set(cls.parked.ids)]})

    def _project(self):
        return super()._project('TWP Hangar 4', stage=self.stage_review)

    def _wizard(self, action):
        return Form(self.env[action['res_model']].with_context(action['context']))

    def _queue(self, project):
        self.env.flush_all()
        self.env['twp.bid.spec.followup'].invalidate_model()
        return self.env['twp.bid.spec.followup'].search([('lead_id', '=', project.id)])

    def _pursue(self, project, lines):
        form = self._wizard(project.action_twp_bs_review())
        form.decision = 'pursue'
        for line in lines:
            form.product_line_ids.add(line)
        form.save().action_apply()

    def _log_quote(self, project, contractor, line=None, quoted=True, amount=0, next_date=None):
        form = self._wizard(project.action_twp_bs_log_quote())
        if line:
            form.product_line_id = line
        form.partner_id = contractor
        form.quoted = quoted
        if quoted:
            form.amount = amount
            form.margin = 0.2
        form.next_date = next_date or self.today + timedelta(days=7)
        form.save().action_apply()

    def test_review_pursue_creates_jobs(self):
        project = self._project()
        self._pursue(project, [self.infrared, self.hvls])
        self.assertEqual(project.stage_id, self.stage_bidding)
        self.assertEqual(project.twp_bs_job_ids.product_line_id, self.infrared | self.hvls)

    def test_review_pass_with_side_lead(self):
        project = self._project()
        self.env.company.write({'twp_bs_side_lead_team_id': self.parked.id,
                                'twp_bs_side_lead_stage_id': self.stage_parked.id})
        form = self._wizard(project.action_twp_bs_review())
        form.decision = 'pass'
        form.lost_reason_id = self.no_scope
        form.side_lead = True
        form.side_lead_name = "GC's warehouse next door"
        form.save().action_apply()
        self.assertEqual(project.won_status, 'lost')
        self.assertEqual(project.lost_reason_id, self.no_scope)
        side = self.env['crm.lead'].search([('twp_bs_origin_lead_id', '=', project.id)])
        self.assertEqual(side.team_id, self.parked)
        self.assertEqual(side.stage_id, self.stage_parked)
        self.assertTrue(side.active)

    def test_log_quote_then_touch(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        # A contact first, no quote yet: Not Quoted, and in the queue.
        self._log_quote(project, self.contractor_a, quoted=False)
        quote = project.twp_bs_quote_ids
        self.assertEqual(quote.result, 'not_quoted')
        self.assertEqual(quote.first_contact_date, self.today)
        self.assertEqual(len(quote.activity_ids), 1)
        self.assertEqual(len(self._queue(project)), 1)
        # Then the quote, on the same line: updates it, closes the old follow-up, opens a new one.
        self._log_quote(project, self.contractor_a, amount=48500, next_date=self.today + timedelta(days=3))
        self.assertEqual(len(project.twp_bs_quote_ids), 1)
        self.assertEqual((quote.quote_date, quote.amount, quote.result), (self.today, 48500, 'pending'))
        self.assertEqual(quote.activity_ids.date_deadline, self.today + timedelta(days=3))
        # A touch moves last contact and the follow-up.
        form = Form(self.env['twp.bid.spec.touch'].with_context(quote.action_twp_bs_log_touch()['context']))
        form.note = 'Still waiting on the GC'
        form.next_date = self.today + timedelta(days=10)
        form.save().action_apply()
        self.assertEqual(quote.last_contact_date, self.today)
        self.assertEqual(quote.activity_ids.date_deadline, self.today + timedelta(days=10))
        self.assertEqual(self._queue(project).date_deadline, self.today + timedelta(days=10))

    def test_log_quote_creates_missing_job(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        self._log_quote(project, self.contractor_a, line=self.hvls, amount=12000)
        self.assertEqual(project.twp_bs_job_ids.product_line_id, self.infrared | self.hvls)

    def test_award_decides_and_empties_the_queue(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        self._log_quote(project, self.contractor_a, amount=48500)
        self._log_quote(project, self.contractor_b, amount=51500)
        self.assertEqual(len(self._queue(project)), 2)
        form = self._wizard(project.action_twp_bs_award())
        self.assertEqual(form.quoted_partner_ids.ids, (self.contractor_a | self.contractor_b).ids)
        form.awarded_partner_id = self.contractor_a
        with form.line_ids.edit(0) as line:
            self.assertEqual(line.quoted_partner_ids.ids, (self.contractor_a | self.contractor_b).ids)
            line.installed_partner_id = self.ours
        form.save().action_apply()
        self.assertEqual(project.twp_bs_status, 'awarded')
        results = {q.partner_id: q.result for q in project.twp_bs_quote_ids}
        self.assertEqual(results, {self.contractor_a: 'won', self.contractor_b: 'lost_contractor'})
        self.assertFalse(self._queue(project))

    def _award(self, project, contractor, installed=None, through=None):
        form = self._wizard(project.action_twp_bs_award())
        form.awarded_partner_id = contractor
        form.bought_through_partner_id = through or self.env['res.partner']
        for index in range(len(form.line_ids)):
            with form.line_ids.edit(index) as line:
                line.installed_partner_id = installed or self.env['res.partner']
        form.save().action_apply()

    def test_bought_through_a_distributor_is_the_distributors_win(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        distributor = self.env['res.partner'].create({'name': 'TWP C Equipment'})
        self._log_quote(project, distributor, amount=45000)
        self._log_quote(project, self.contractor_a, amount=48500)
        self._award(project, self.contractor_a, self.ours, through=distributor)
        results = {q.partner_id: q.result for q in project.twp_bs_quote_ids}
        self.assertEqual(results, {distributor: 'won', self.contractor_a: 'lost_contractor'})
        self.assertEqual(project.twp_bs_job_ids.won_amount, 45000)

    def test_award_with_unknown_equipment_waits_for_update(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        self._log_quote(project, self.contractor_a, amount=48500)
        form = self._wizard(project.action_twp_bs_award())
        form.awarded_partner_id = self.contractor_a
        form.save().action_apply()
        self.assertEqual(project.twp_bs_quote_ids.result, 'awarded_update')

    def test_cancelled_project_drops_its_follow_ups(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        self._log_quote(project, self.contractor_a, amount=48500)
        action = project.action_twp_bs_project_dead()
        self.assertEqual(action['context']['default_lost_reason_id'], self.cancelled.id)
        wizard = self.env['crm.lead.lost'].with_context(action['context']).create({})
        wizard.action_lost_reason_apply()
        self.assertEqual(project.twp_bs_status, 'cancelled')
        self.assertEqual(project.twp_bs_quote_ids.result, 'project_dead')
        self.assertFalse(project.twp_bs_quote_ids.activity_ids)
        self.assertFalse(self._queue(project))

    def test_project_activity_is_in_the_queue(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        project.activity_schedule('mail.mail_activity_data_todo', date_deadline=self.today, summary='Find the GC')
        row = self._queue(project)
        self.assertEqual((row.summary, row.quote_id.id), ('Find the GC', False))
        self.assertEqual(row.action_open()['res_model'], 'crm.lead')

    def test_review_without_side_leads_set_up(self):
        self.env.company.twp_bs_side_lead_team_id = False
        form = self._wizard(self._project().action_twp_bs_review())
        self.assertFalse(form.side_leads_enabled)

    def test_follow_up_days_come_from_settings(self):
        self.env.company.twp_bs_followup_days = 3
        form = self._wizard(self._project().action_twp_bs_log_quote())
        self.assertEqual(form.next_date, self.today + timedelta(days=3))

    def test_award_needs_an_awarded_stage(self):
        project = self._project()
        self._pursue(project, [self.infrared])
        self._log_quote(project, self.contractor_a, amount=48500)
        self.stage_awarded.twp_bs_step = 'done'
        self.stage_closed.twp_bs_step = False
        with self.assertRaises(UserError):
            self._award(project, self.contractor_a, self.ours)
