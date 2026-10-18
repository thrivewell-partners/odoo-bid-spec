from datetime import timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TwpBidSpecCase


@tagged("post_install", "-at_install")
class TestSetup(TwpBidSpecCase):
    """Which pipeline is Bid / Spec, what each stage means, and the settings, all chosen by the admin."""

    def test_a_pipeline_is_bid_spec_by_its_tick(self):
        project = self._project()
        self.assertTrue(project.twp_bs_is_bid_spec)
        other = self.env["crm.team"].create({"name": "TWP Other"})
        lead = self.env["crm.lead"].create({"name": "TWP Plain", "type": "opportunity", "team_id": other.id})
        self.assertFalse(lead.twp_bs_is_bid_spec)
        self.assertFalse(lead.twp_bs_status, "No bid status off Bid / Spec")
        other.twp_bs_enabled = True
        self.assertTrue(lead.twp_bs_is_bid_spec)

    def test_status_follows_the_step(self):
        project = self._project(stage=self.stage_review)
        for stage, status in [(self.stage_review, "bidding"), (self.stage_bidding, "bidding"),
                              (self.stage_opened, "opened"), (self.stage_awarded, "awarded"),
                              (self.stage_closed, "awarded")]:
            project.stage_id = stage
            self.assertEqual(project.twp_bs_status, status, stage.name)
        project.action_set_lost(lost_reason_id=self.cancelled.id)
        self.assertEqual(project.twp_bs_status, "cancelled")

    def test_bid_date_is_required_by_setting(self):
        with self.assertRaises(ValidationError):
            self._project(twp_bs_bid_date=False)
        self.env.company.twp_bs_bid_date_required = False
        self.assertFalse(self._project(twp_bs_bid_date=False).twp_bs_bid_date)

    def test_other_pipelines_need_no_bid_date(self):
        other = self.env["crm.team"].create({"name": "TWP Other"})
        lead = self.env["crm.lead"].create({"name": "TWP Plain", "type": "opportunity", "team_id": other.id})
        self.assertFalse(lead.twp_bs_bid_date)

    def test_create_pipeline_from_settings(self):
        self.env["res.config.settings"].create({}).action_twp_bs_create_pipeline()
        team = self.env["crm.team"].search([("twp_bs_enabled", "=", True)], order="id desc", limit=1)
        self.assertNotEqual(team, self.team)
        self.assertTrue(team.twp_bs_enabled)
        stages = self.env["crm.stage"].search([("team_ids", "in", team.ids)], order="sequence")
        self.assertEqual(stages.mapped("twp_bs_step"), ["review", "bidding", "closed", "awarded", "done"])
        self.assertFalse(stages.filtered("is_won"), "Wins are counted per job, never by Odoo's Won")

    def test_pipeline_menu_opens_every_bid_spec_board(self):
        second = self.env["crm.team"].create({"name": "TWP Second", "twp_bs_enabled": True})
        action = self.env["crm.lead"].action_twp_bs_pipeline()
        teams = dict((term[0], term[2]) for term in action["domain"])["team_id"]
        self.assertTrue({self.team.id, second.id} <= set(teams))
        lead = self.env["crm.lead"].with_context(action["context"]).create(
            {"name": "TWP Probe", "twp_bs_bid_date": self.today})
        self.assertTrue(lead.twp_bs_is_bid_spec)

    def test_past_bids_move_to_bidding_closed(self):
        # The night after its bid date, a Bidding card moves on; Review and future bids stay put.
        Lead = self.env["crm.lead"]

        def card(stage, days):
            return self._project("TWP Probe", stage=stage, twp_bs_bid_date=self.today + timedelta(days=days))
        past, due_today, future, in_review = (card(self.stage_bidding, -1), card(self.stage_bidding, 0),
                                              card(self.stage_bidding, 5), card(self.stage_review, -3))
        self.assertEqual(self.env.ref("twp_bid_spec.cron_close_past_bids").code,
                         "model._twp_bs_cron_close_past_bids()")
        Lead._twp_bs_cron_close_past_bids()
        self.assertEqual(past.stage_id, self.stage_opened)
        self.assertEqual(past.twp_bs_status, "opened")
        self.assertEqual(due_today.stage_id, self.stage_bidding)
        self.assertEqual(future.stage_id, self.stage_bidding)
        self.assertEqual(in_review.stage_id, self.stage_review)

    def test_closing_after_the_bid_date_can_be_turned_off(self):
        past = self._project(twp_bs_bid_date=self.today - timedelta(days=1))
        self.env.company.twp_bs_close_after_bid_date = False
        self.env["crm.lead"]._twp_bs_cron_close_past_bids()
        self.assertEqual(past.stage_id, self.stage_bidding)

    def test_new_contact_takes_the_role_of_its_field(self):
        engineer_role = self.env["twp.bid.spec.partner.role"].create({"name": "TWP Engineer", "kind": "engineer",
                                                                     "sequence": -1})
        partner = self.env["res.partner"].with_context(twp_bs_role_kind="engineer").create({"name": "TWP Firm"})
        self.assertEqual(partner.twp_bs_role_ids, engineer_role)
        plain = self.env["res.partner"].create({"name": "TWP Plain Contact"})
        self.assertFalse(plain.twp_bs_role_ids)

    def test_stage_requirements_still_apply_off_bidding(self):
        # Bid / Spec's own warnings come first; once it has none, the stage's requirements show.
        field = self.env["ir.model.fields"]._get("crm.lead", "partner_id")
        self.stage_awarded.twp_requirement_ids = [Command.create({"field_id": field.id, "message": "TWP No customer"})]
        project = self._project(stage=self.stage_awarded)
        self.assertEqual(project.twp_needs_attention, "TWP No customer")
