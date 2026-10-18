from odoo import Command, _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    twp_bs_team_ids = fields.Many2many(
        "crm.team", string="Bid / Spec pipelines", compute="_compute_twp_bs_team_ids")
    twp_bs_bid_date_required = fields.Boolean(related="company_id.twp_bs_bid_date_required", readonly=False)
    twp_bs_close_after_bid_date = fields.Boolean(related="company_id.twp_bs_close_after_bid_date", readonly=False)
    twp_bs_followup_days = fields.Integer(related="company_id.twp_bs_followup_days", readonly=False)
    twp_bs_warning_days = fields.Integer(related="company_id.twp_bs_warning_days", readonly=False)
    twp_bs_due_window_days = fields.Integer(related="company_id.twp_bs_due_window_days", readonly=False)
    twp_bs_cancelled_reason_id = fields.Many2one(related="company_id.twp_bs_cancelled_reason_id", readonly=False)
    twp_bs_side_lead_team_id = fields.Many2one(related="company_id.twp_bs_side_lead_team_id", readonly=False)
    twp_bs_side_lead_stage_id = fields.Many2one(related="company_id.twp_bs_side_lead_stage_id", readonly=False)

    def _compute_twp_bs_team_ids(self):
        self.twp_bs_team_ids = self.env["crm.team"].search([("twp_bs_enabled", "=", True)])

    def action_twp_bs_create_pipeline(self):
        """A Bid / Spec pipeline with its five stages, for a database that has none yet."""
        stages = [
            (_("Review"), "review", False),
            (_("Bidding"), "bidding", False),
            (_("Bidding Closed"), "closed", False),
            (_("Awarded"), "awarded", False),
            (_("Closed"), "done", True),
        ]
        team = self.env["crm.team"].create({
            "name": _("Bid / Spec"),
            "use_opportunities": True,
            "twp_bs_enabled": True,
        })
        self.env["crm.stage"].create([{
            "name": name,
            "sequence": sequence,
            "fold": fold,
            "twp_bs_step": step,
            "team_ids": [Command.set(team.ids)],
        } for sequence, (name, step, fold) in enumerate(stages, start=1)])
        return self.env["crm.lead"].action_twp_bs_pipeline()
