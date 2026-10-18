from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase


class TwpBidSpecCase(TransactionCase):
    """A Bid / Spec pipeline, stages and product lines of the test's own, so nothing depends on the
    database's data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env["crm.team"].create({"name": "TWP Bid Spec", "twp_bs_enabled": True})
        Stage = cls.env["crm.stage"]

        def stage(name, sequence, step, **vals):
            return Stage.create({"name": name, "sequence": sequence, "twp_bs_step": step,
                                 "team_ids": [Command.set(cls.team.ids)], **vals})
        cls.stage_review = stage("TWP Review", 1, "review")
        cls.stage_bidding = stage("TWP Bidding", 2, "bidding")
        cls.stage_opened = stage("TWP Bidding Closed", 3, "closed")
        cls.stage_awarded = stage("TWP Awarded", 4, "awarded")
        cls.stage_closed = stage("TWP Closed", 5, "done", fold=True)
        Line = cls.env["twp.bid.spec.product.line"]
        cls.infrared = Line.create({"name": "TWP Infrared Heating"})
        cls.hvls = Line.create({"name": "TWP HVLS Fans"})
        cls.cancelled = cls.env.ref("twp_bid_spec.lost_reason_cancelled")
        cls.no_scope = cls.env["crm.lost.reason"].create({"name": "TWP No scope"})
        cls.env.company.write({
            "twp_bs_cancelled_reason_id": cls.cancelled.id,
            "twp_bs_bid_date_required": True,
            "twp_bs_close_after_bid_date": True,
            "twp_bs_followup_days": 7,
            "twp_bs_warning_days": 7,
            "twp_bs_due_window_days": 14,
        })
        Partner = cls.env["res.partner"]
        cls.ours = Partner.create({"name": "TWP Our IR Mfr", "twp_bs_we_represent": True})
        cls.theirs = Partner.create({"name": "TWP Other IR Mfr"})
        cls.contractor_a = Partner.create({"name": "TWP A Mechanical"})
        cls.contractor_b = Partner.create({"name": "TWP B Heating & Air"})
        cls.today = fields.Date.context_today(cls.env["crm.lead"])

    @classmethod
    def _project(cls, name="TWP Lincoln Distribution Warehouse", stage=None, **vals):
        return cls.env["crm.lead"].create({
            "name": name,
            "type": "opportunity",
            "team_id": cls.team.id,
            "stage_id": (stage or cls.stage_bidding).id,
            "twp_bs_bid_date": cls.today + timedelta(days=30),
            **vals,
        })
