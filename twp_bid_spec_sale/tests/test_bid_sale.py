from datetime import timedelta

from odoo import Command
from odoo.tests import Form, tagged

from odoo.addons.twp_bid_spec.tests.common import TwpBidSpecCase


@tagged('post_install', '-at_install')
class TestBidSale(TwpBidSpecCase):
    """Bids built in Sales fill the contractor bids; Award turns the winner into the quotation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.distributor = cls.env['res.partner'].create({'name': 'TWP C Equipment'})

    def _line(self, product_line, name, qty, price, cost):
        return Command.create({
            'product_id': product_line._twp_bs_sale_product().id,
            'name': name,
            'product_uom_qty': qty,
            'price_unit': price,
            'purchase_price': cost,
        })

    def _bid(self, project, partner, lines=None):
        return self.env['sale.order'].with_context(default_twp_is_bid=True).create({
            'partner_id': partner.id,
            'opportunity_id': project.id,
            'twp_bs_quoted_as': 'bod',
            'order_line': lines or [self._line(self.infrared, 'HL3-30-125N tube heater', 3, 1655.94, 1000.0)],
        })

    def _jobs(self, project, lines):
        for line in lines:
            self.env['twp.bid.spec.job'].create({'lead_id': project.id, 'product_line_id': line.id})
        return project

    def _award(self, project, contractor, installed=None, through=None):
        form = Form(self.env['twp.bid.spec.award'].with_context(project.action_twp_bs_award()['context']))
        form.awarded_partner_id = contractor
        form.bought_through_partner_id = through or self.env['res.partner']
        for index in range(len(form.line_ids)):
            with form.line_ids.edit(index) as line:
                line.installed_partner_id = installed or self.env['res.partner']
        form.save().action_apply()

    def _log(self, project, partner, amount, line=None):
        return self.env['twp.bid.spec.quote'].create({
            'job_id': project.twp_bs_job_ids.filtered(lambda j: j.product_line_id == (line or self.infrared)).id,
            'partner_id': partner.id, 'quote_date': self.today, 'amount': amount, 'margin': 0.2,
        })

    def _quotations(self, project):
        return self.env['sale.order'].search([
            ('opportunity_id', '=', project.id), ('state', '!=', 'cancel'), ('twp_is_bid', '=', False)])

    def _cancel(self, project):
        action = project.action_twp_bs_project_dead()
        self.env['crm.lead.lost'].with_context(action['context']).create({}).action_lost_reason_apply()

    # Bids built in Sales

    def test_product_lines_have_sales_products(self):
        for line in self.infrared | self.hvls:
            self.assertEqual(line.product_id.twp_bs_product_line_id, line)
        new = self.env['twp.bid.spec.product.line'].create({'name': 'TWP Snowmelt'})
        self.assertEqual(new.product_id.twp_bs_product_line_id, new)

    def test_bid_fills_the_contractor_bid(self):
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a)
        row = project.twp_bs_quote_ids
        self.assertEqual((row.partner_id, row.job_id.product_line_id, row.sale_order_id), (self.contractor_a, self.infrared, bid))
        self.assertAlmostEqual(row.amount, 4967.82)
        self.assertAlmostEqual(row.margin, 1 - 3000 / 4967.82, places=4)
        self.assertEqual((row.model_quoted, row.quoted_as), ('HL3-30-125N tube heater', 'bod'))
        self.assertEqual(row.result, 'not_quoted', "Built but not sent")
        bid.write({'order_line': [Command.update(bid.order_line.id, {'price_unit': 1500.0})]})
        self.assertAlmostEqual(row.amount, 4500.0)

    def test_one_bid_fills_every_job_it_carries(self):
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a, [
            self._line(self.infrared, 'HL3-30-125N', 3, 1655.94, 1000.0),
            self._line(self.hvls, 'HVLS 16 ft', 1, 6000.0, 4000.0),
        ])
        self.assertEqual(project.twp_bs_job_ids.product_line_id, self.infrared | self.hvls, "The fans job is made from the bid")
        amounts = {row.job_id.product_line_id: row.amount for row in project.twp_bs_quote_ids}
        self.assertEqual(amounts, {self.infrared: 4967.82, self.hvls: 6000.0})
        self.assertEqual(project.twp_bs_quote_ids.sale_order_id, bid)
        self.assertFalse(bid.twp_bs_unmatched_lines)

    def test_unmatched_lines_are_flagged(self):
        project = self._jobs(self._project(), [self.infrared, self.hvls])
        loose = self.env['product.product'].create({'name': 'TWP Freight', 'type': 'service'})
        bid = self._bid(project, self.contractor_a, [
            self._line(self.infrared, 'HL3-30-125N', 3, 1655.94, 1000.0),
            Command.create({'product_id': loose.id, 'product_uom_qty': 1, 'price_unit': 375.0}),
        ])
        self.assertIn('TWP Freight', bid.twp_bs_unmatched_lines)
        self.assertAlmostEqual(project.twp_bs_quote_ids.amount, 4967.82, msg="Freight counts toward no job")

    def test_alternatives_not_chosen_stay_out_of_the_bid(self):
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a, [
            Command.create({'display_type': 'line_section', 'name': 'Option 1', 'twp_option_mode': 'alternative'}),
            self._line(self.infrared, 'HL3-30-125N', 3, 1655.94, 1000.0),
            Command.create({'display_type': 'line_section', 'name': 'Option 2', 'twp_option_mode': 'alternative'}),
            self._line(self.infrared, 'HL3-40-150N', 3, 2000.0, 1300.0),
        ])
        self.assertFalse(project.twp_bs_quote_ids.amount, "Nothing is chosen, so the bid counts nothing yet")
        option_2 = bid.order_line.filtered(lambda line: line.name == 'Option 2')
        bid.write({'order_line': [Command.update(option_2.id, {'twp_option_chosen': True})]})
        self.assertAlmostEqual(project.twp_bs_quote_ids.amount, 6000.0)
        self.assertEqual(project.twp_bs_quote_ids.amount, bid.amount_untaxed)

    def test_sending_stamps_bid_sent_and_books_the_follow_up(self):
        self.env.company.twp_bs_followup_days = 5
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a)
        bid.action_quotation_sent()
        row = project.twp_bs_quote_ids
        self.assertEqual((row.quote_date, row.last_contact_date), (self.today, self.today))
        self.assertEqual(row.result, 'pending')
        self.assertEqual(row.activity_ids.date_deadline, self.today + timedelta(days=5))
        self.assertIn(bid.name, row.message_ids[0].body)

    def test_copy_to_contractors_fills_a_bid_each(self):
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a)
        wizard = Form(self.env['twp.bid.copy'].with_context(default_bid_id=bid.id))
        wizard.partner_ids.add(self.contractor_b)
        wizard.save().action_apply()
        rows = {row.partner_id: row for row in project.twp_bs_quote_ids}
        self.assertEqual(set(rows), {self.contractor_a, self.contractor_b})
        self.assertNotEqual(rows[self.contractor_b].sale_order_id, bid)
        self.assertEqual(rows[self.contractor_b].amount, rows[self.contractor_a].amount)

    def test_won_on_a_bid_opens_award(self):
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a)
        action = bid.action_twp_bid_won()
        self.assertEqual(action['res_model'], 'twp.bid.spec.award')
        award = Form(self.env['twp.bid.spec.award'].with_context(action['context']))
        self.assertEqual(award.awarded_partner_id, self.contractor_a)
        self.assertTrue(bid.twp_is_bid, "Nothing is won until Award is applied")

    def test_bids_off_bid_spec_are_left_alone(self):
        lead = self.env['crm.lead'].create({'name': 'TWP Plain opportunity', 'type': 'opportunity'})
        bid = self._bid(lead, self.contractor_a)
        self.assertFalse(bid.twp_bs_is_bid_spec)
        self.assertFalse(self.env['twp.bid.spec.quote'].search([('sale_order_id', '=', bid.id)]))
        bid.action_quotation_sent()
        self.assertTrue(bid.action_twp_bid_won())
        self.assertEqual((bid.twp_is_bid, bid.twp_bid_status), (False, 'won'), "Won works as Bids has it")

    # Award

    def test_award_turns_the_winning_bid_into_the_quotation(self):
        project = self._jobs(self._project(), [self.infrared])
        bid_a = self._bid(project, self.contractor_a)
        bid_b = self._bid(project, self.contractor_b)
        (bid_a | bid_b).action_quotation_sent()
        self._award(project, self.contractor_a, self.ours)
        self.assertEqual(project.twp_bs_sale_order_id, bid_a, "The bid itself, not a copy")
        self.assertEqual((bid_a.twp_is_bid, bid_a.twp_bid_status, bid_a.state), (False, 'won', 'draft'))
        self.assertNotEqual(bid_a.name, bid_a.twp_bid_number)
        self.assertIn(bid_a.name, project.message_ids[0].body)
        self.assertEqual((bid_b.twp_bid_status, bid_b.state), ('lost', 'cancel'))
        self.assertEqual(project.quotation_count, 1)
        results = {q.partner_id: q.result for q in project.twp_bs_quote_ids}
        self.assertEqual(results, {self.contractor_a: 'won', self.contractor_b: 'lost_contractor'})
        # The award moves: the first quotation is cancelled, the other bid wins.
        self._award(project, self.contractor_b, self.ours)
        self.assertEqual(project.twp_bs_sale_order_id, bid_b)
        self.assertEqual((bid_b.twp_bid_status, bid_b.state), ('won', 'draft'))
        self.assertEqual((bid_a.twp_bid_status, bid_a.state), ('lost', 'cancel'))
        # And back: the first quotation opens again, rather than a cancelled one being named.
        self._award(project, self.contractor_a, self.ours)
        self.assertEqual(project.twp_bs_sale_order_id, bid_a)
        self.assertEqual((bid_a.twp_bid_status, bid_a.state), ('won', 'draft'))
        self.assertEqual((bid_b.twp_bid_status, bid_b.state), ('lost', 'cancel'))

    def test_distributor_bid_wins_when_bought_through(self):
        project = self._jobs(self._project(), [self.infrared])
        bid_c = self._bid(project, self.distributor)
        bid_a = self._bid(project, self.contractor_a)
        (bid_c | bid_a).action_quotation_sent()
        self._award(project, self.contractor_a, self.ours, through=self.distributor)
        self.assertEqual(project.twp_bs_sale_order_id, bid_c)
        self.assertEqual(bid_a.twp_bid_status, 'lost')

    def test_cancelled_project_loses_every_bid(self):
        project = self._jobs(self._project(), [self.infrared])
        bid = self._bid(project, self.contractor_a)
        self._cancel(project)
        self.assertEqual((bid.twp_bid_status, bid.state), ('lost', 'cancel'))

    def test_logged_bid_still_makes_its_quotation(self):
        project = self._jobs(self._project(), [self.infrared])
        self._log(project, self.contractor_a, 48500)
        self._award(project, self.contractor_a, self.ours)
        order = project.twp_bs_sale_order_id
        self.assertEqual((order.partner_id, order.order_line.price_unit), (self.contractor_a, 48500))
        self.assertEqual((order.state, order.team_id), ('draft', project.team_id))
        self.assertEqual(order.order_line.product_id, self.infrared.product_id)
        self.assertEqual(order.order_line.purchase_price, 38800, "The bid's 20% margin carried as cost")
        self.assertFalse(order.twp_bid_number)
        self.assertEqual(project.twp_bs_job_ids.sale_order_id, order)

    def test_award_makes_one_quotation_for_the_winner(self):
        project = self._jobs(self._project(), [self.infrared])
        self._log(project, self.contractor_a, 48500)
        self._log(project, self.contractor_b, 51500)
        self._award(project, self.contractor_a, self.ours)
        order = project.twp_bs_sale_order_id
        self.assertEqual(self._quotations(project), order, "The losing bid does not reach Sales")
        # Awarding again changes nothing; moving the award replaces the open quotation.
        self._award(project, self.contractor_a, self.ours)
        self.assertEqual(self._quotations(project), order)
        self._award(project, self.contractor_b, self.ours)
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(self._quotations(project).partner_id, self.contractor_b)
        self.assertEqual(self._quotations(project).order_line.price_unit, 51500)

    def test_award_without_our_win_makes_no_quotation(self):
        project = self._jobs(self._project(), [self.infrared])
        self._log(project, self.contractor_a, 48500)
        # A contractor we never bid to, then ours with equipment not known, then another maker's.
        self._award(project, self.contractor_b)
        self.assertFalse(self._quotations(project))
        self._award(project, self.contractor_a)
        self.assertEqual(len(self._quotations(project)), 1, "Equipment not known yet still quotes the winner")
        self._award(project, self.contractor_a, self.theirs)
        self.assertEqual(project.twp_bs_quote_ids.result, 'lost_mfr')
        self.assertFalse(self._quotations(project))

    def test_cancelled_project_cancels_its_quotation(self):
        project = self._jobs(self._project(), [self.infrared])
        self._log(project, self.contractor_a, 48500)
        self._award(project, self.contractor_a, self.ours)
        order = project.twp_bs_sale_order_id
        self._cancel(project)
        self.assertEqual(order.state, 'cancel')

    def test_one_quotation_for_a_project_of_several_jobs(self):
        project = self._jobs(self._project(), [self.infrared, self.hvls])
        self._log(project, self.contractor_a, 48500)
        self._log(project, self.contractor_a, 12000, line=self.hvls)
        self._log(project, self.contractor_b, 51500)
        self._award(project, self.contractor_a, self.ours)
        order = self._quotations(project)
        self.assertEqual(len(order), 1, "One quotation for the project, not one per job")
        self.assertEqual(order.partner_id, self.contractor_a)
        self.assertEqual(sorted(order.order_line.mapped('price_unit')), [12000, 48500])
        self.assertEqual(project.twp_bs_job_ids.sale_order_id, order)
