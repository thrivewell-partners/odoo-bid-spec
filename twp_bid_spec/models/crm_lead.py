from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .crm_stage import STATUS_OF_STEP, STEPS
from .twp_bid_spec_quote import DECIDED_RESULTS


class CrmLead(models.Model):
    """On a Bid / Spec pipeline, an opportunity is a project: jobs, contractor bids, and the award."""

    _inherit = "crm.lead"

    twp_bs_is_bid_spec = fields.Boolean(
        related="team_id.twp_bs_enabled", string="Is Bid / Spec", store=True, index=True)
    twp_bs_step = fields.Selection(related="stage_id.twp_bs_step", string="Bid / Spec step")
    twp_bs_status = fields.Selection([
        ("bidding", "Bidding"),
        ("opened", "Bidding Closed"),
        ("awarded", "Awarded"),
        ("cancelled", "Cancelled / Postponed"),
    ], string="Bid status", compute="_compute_twp_bs_status", store=True)
    twp_bs_bid_date_required = fields.Boolean(compute="_compute_twp_bs_bid_date_required")
    twp_bs_project_type_id = fields.Many2one("twp.bid.spec.project.type", string="Project type")
    twp_bs_bid_date = fields.Date("Bid date")
    twp_bs_architect_id = fields.Many2one("res.partner", string="Architect")
    twp_bs_engineer_id = fields.Many2one("res.partner", string="Mechanical engineer", index=True)
    twp_bs_gc_id = fields.Many2one("res.partner", string="General contractor")
    twp_bs_owner_id = fields.Many2one("res.partner", string="Owner")
    twp_bs_plans_url = fields.Char("Plans / spec link")
    twp_bs_lead_reference = fields.Char("Lead reference", help="The project's number at the lead service.")
    twp_bs_substitution_note = fields.Text("Substitution note")
    twp_bs_hold_id = fields.Many2one("twp.bid.spec.hold", string="Hold")
    twp_bs_hold_note = fields.Char("Hold note")
    twp_bs_origin_lead_id = fields.Many2one(
        "crm.lead", string="Side lead of", index="btree_not_null", ondelete="set null",
        help="The Bid / Spec project this lead was spotted in.")

    twp_bs_job_ids = fields.One2many("twp.bid.spec.job", "lead_id", string="Jobs")
    twp_bs_quote_ids = fields.One2many("twp.bid.spec.quote", "lead_id", string="Bids")
    twp_bs_job_count = fields.Integer("Number of jobs", compute="_compute_twp_bs_figures", store=True)
    twp_bs_quote_count = fields.Integer("Contractor lines", compute="_compute_twp_bs_figures", store=True)
    twp_bs_quotes_sent_count = fields.Integer("Lines bid", compute="_compute_twp_bs_figures", store=True)
    twp_bs_quotes_won_count = fields.Integer("Lines won", compute="_compute_twp_bs_figures", store=True)
    twp_bs_quotes_decided_count = fields.Integer("Lines decided", compute="_compute_twp_bs_figures", store=True)
    twp_bs_days_to_bid = fields.Integer("Days to bid", compute="_compute_twp_bs_days_to_bid")

    @api.depends("twp_bs_is_bid_spec", "stage_id.twp_bs_step", "won_status")
    def _compute_twp_bs_status(self):
        for lead in self:
            if not lead.twp_bs_is_bid_spec:
                lead.twp_bs_status = False
            elif lead.won_status == "lost":
                lead.twp_bs_status = "cancelled"
            else:
                lead.twp_bs_status = STATUS_OF_STEP.get(lead.stage_id.twp_bs_step, False)

    @api.depends("company_id")
    def _compute_twp_bs_bid_date_required(self):
        for lead in self:
            lead.twp_bs_bid_date_required = (lead.company_id or self.env.company).twp_bs_bid_date_required

    @api.depends("twp_bs_job_ids", "twp_bs_quote_ids.quote_date", "twp_bs_quote_ids.result")
    def _compute_twp_bs_figures(self):
        for lead in self:
            quotes = lead.twp_bs_quote_ids
            won = len(quotes.filtered(lambda q: q.result == "won"))
            lead.twp_bs_job_count = len(lead.twp_bs_job_ids)
            lead.twp_bs_quote_count = len(quotes)
            lead.twp_bs_quotes_sent_count = len(quotes.filtered("quote_date"))
            lead.twp_bs_quotes_won_count = won
            # An award still waiting on an update, with nothing won yet, decides nothing.
            if not won and any(q.result == "awarded_update" for q in quotes):
                lead.twp_bs_quotes_decided_count = 0
            else:
                lead.twp_bs_quotes_decided_count = len(quotes.filtered(lambda q: q.result in DECIDED_RESULTS))

    @api.depends("twp_bs_bid_date")
    def _compute_twp_bs_days_to_bid(self):
        today = fields.Date.context_today(self)
        for lead in self:
            lead.twp_bs_days_to_bid = (lead.twp_bs_bid_date - today).days if lead.twp_bs_bid_date else 0

    @api.model
    def _twp_attention_depends(self):
        return super()._twp_attention_depends() + [
            "twp_bs_bid_date", "twp_bs_status", "twp_bs_quote_count", "twp_bs_quotes_sent_count"]

    def _twp_attention(self):
        if self.active and self.twp_bs_status == "bidding":
            company = self.company_id or self.env.company
            # Only cards from before the bid date was required can lack one.
            if not self.twp_bs_bid_date:
                return _("No bid date")
            if not self.twp_bs_quote_count:
                return _("No contractors contacted")
            if 0 <= self.twp_bs_days_to_bid <= company.twp_bs_warning_days and not self.twp_bs_quotes_sent_count:
                return _("Bid within %s days - no bid sent", company.twp_bs_warning_days)
        return super()._twp_attention()

    @api.constrains("twp_bs_bid_date", "team_id", "type", "active")
    def _check_twp_bs_bid_date(self):
        missing = self.filtered(lambda lead: lead.twp_bs_is_bid_spec and lead.type == "opportunity"
                                and lead.active and not lead.twp_bs_bid_date and lead.twp_bs_bid_date_required)
        if missing:
            raise ValidationError(_("A Bid / Spec project needs a bid date: %s", ", ".join(missing.mapped("name"))))

    @api.model
    def _twp_bs_cron_close_past_bids(self):
        # Bid day has passed, so nothing more can be bid: the card waits on the award. Review is
        # left alone, since a project still being looked over has not been bid.
        past = self.search([
            ("twp_bs_is_bid_spec", "=", True),
            ("stage_id.twp_bs_step", "=", "bidding"),
            ("twp_bs_bid_date", "<", fields.Date.context_today(self)),
        ])
        past = past.filtered(lambda lead: (lead.company_id or self.env.company).twp_bs_close_after_bid_date)
        for team, leads in past.grouped("team_id").items():
            closed = team._twp_bs_stage("closed")
            if closed:
                leads.stage_id = closed

    def _twp_bs_move_to(self, step):
        """Move each project to its pipeline's first stage at this step."""
        for team, leads in self.grouped("team_id").items():
            stage = team._twp_bs_stage(step) if team else self.env["crm.stage"]
            if not stage:
                label = dict(STEPS)[step]
                raise UserError(_(
                    "The %(team)s pipeline has no stage with the %(step)s step. Set one under "
                    "CRM > Configuration > Stages.", team=team.name or _("(no team)"), step=label))
            leads.stage_id = stage

    def action_set_lost(self, **additional_values):
        # A dead or passed project needs no more chasing: drop the follow-ups on its bids.
        res = super().action_set_lost(**additional_values)
        activities = self.twp_bs_quote_ids.activity_ids
        if activities:
            activities.unlink()
        return res

    def _twp_bs_wizard(self, model, name):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "form",
            "target": "new",
            "context": {"default_lead_id": self.id},
        }

    def action_twp_bs_review(self):
        return self._twp_bs_wizard("twp.bid.spec.review", _("Review"))

    def action_twp_bs_log_quote(self):
        return self._twp_bs_wizard("twp.bid.spec.log.quote", _("Log a bid"))

    def action_twp_bs_award(self):
        return self._twp_bs_wizard("twp.bid.spec.award", _("Award"))

    def action_twp_bs_project_dead(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("crm.crm_lead_lost_action")
        action["name"] = _("Cancelled / postponed")
        action["context"] = {
            "dialog_size": "medium",
            "default_lead_ids": self.ids,
            "default_lost_reason_id": (self.company_id or self.env.company).twp_bs_cancelled_reason_id.id,
        }
        return action

    def action_twp_bs_open_quotes(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("twp_bid_spec.action_twp_bs_quote")
        action["domain"] = [("lead_id", "=", self.id)]
        action["context"] = {"search_default_group_job": 1}
        return action

    @api.model
    def action_twp_bs_pipeline(self):
        """The board of every Bid / Spec pipeline. New cards go to the first one."""
        teams = self.env["crm.team"].search([("twp_bs_enabled", "=", True)])
        if not teams:
            raise UserError(_("No pipeline is set up for Bid / Spec yet. Create one in Settings > CRM > Bid / Spec, "
                              "or tick Bid / Spec on a sales team."))
        action = self.env["ir.actions.actions"]._for_xml_id("crm.crm_lead_action_pipeline")
        action.update({
            "name": _("Bid / Spec"),
            "domain": [("type", "=", "opportunity"), ("team_id", "in", teams.ids)],
            "context": {"default_type": "opportunity", "default_team_id": teams[:1].id},
        })
        return action
