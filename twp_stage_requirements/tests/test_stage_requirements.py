from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStageRequirements(TransactionCase):
    """A stage lists what a card needs there, and can stamp a date when a card arrives."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Field = cls.env["ir.model.fields"]

        def field(name):
            return Field._get("crm.lead", name).id

        cls.team = cls.env["crm.team"].create({"name": "TWP Requirements Team"})
        Stage = cls.env["crm.stage"]
        cls.request = Stage.create({
            "name": "TWP Request", "sequence": 1, "team_ids": [Command.set(cls.team.ids)],
            "twp_requirement_ids": [
                Command.create({"sequence": 1, "field_id": field("partner_id"), "message": "Customer not set"}),
                Command.create({"sequence": 2, "field_id": field("tag_ids"), "message": "No tags"}),
            ],
        })
        cls.quoted = Stage.create({
            "name": "TWP Quoted", "sequence": 2, "team_ids": [Command.set(cls.team.ids)],
            "twp_requirement_ids": [
                Command.create({"field_id": field("expected_revenue"), "message": "Quote $ not entered"}),
            ],
            "twp_stamp_field_id": field("date_deadline"),
        })
        cls.plain = Stage.create({"name": "TWP Plain", "sequence": 3, "team_ids": [Command.set(cls.team.ids)]})
        cls.customer = cls.env["res.partner"].create({"name": "TWP Customer"})
        cls.tag = cls.env["crm.tag"].create({"name": "TWP Tag"})

    def _card(self, stage, **vals):
        return self.env["crm.lead"].create({
            "name": "TWP Card", "type": "opportunity", "team_id": self.team.id, "stage_id": stage.id, **vals})

    def test_first_missing_requirement_is_shown(self):
        card = self._card(self.request)
        self.assertEqual(card.twp_needs_attention, "Customer not set")
        card.partner_id = self.customer
        self.assertEqual(card.twp_needs_attention, "No tags", "The next one, once the first is met")
        card.tag_ids = self.tag
        self.assertFalse(card.twp_needs_attention)

    def test_stage_without_requirements_needs_nothing(self):
        self.assertFalse(self._card(self.plain).twp_needs_attention)

    def test_moving_stage_changes_the_warning(self):
        card = self._card(self.request, partner_id=self.customer.id, tag_ids=[Command.set(self.tag.ids)])
        self.assertFalse(card.twp_needs_attention)
        card.stage_id = self.quoted
        self.assertEqual(card.twp_needs_attention, "Quote $ not entered")
        card.expected_revenue = 3043.44
        self.assertFalse(card.twp_needs_attention)

    def test_won_or_lost_cards_need_nothing(self):
        lost = self._card(self.request)
        lost.action_set_lost()
        self.assertFalse(lost.twp_needs_attention)
        won = self._card(self.quoted)
        won.action_set_won()
        self.assertFalse(won.twp_needs_attention)

    def test_arrival_stamps_the_date(self):
        card = self._card(self.request)
        self.assertFalse(card.date_deadline)
        card.stage_id = self.quoted
        self.assertEqual(card.date_deadline, fields.Date.context_today(card))

    def test_a_date_already_filled_in_is_kept(self):
        card = self._card(self.request, date_deadline="2026-09-29")
        card.stage_id = self.quoted
        self.assertEqual(str(card.date_deadline), "2026-09-29")

    def test_created_in_a_stamping_stage(self):
        card = self._card(self.quoted)
        self.assertEqual(card.date_deadline, fields.Date.context_today(card))
