from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TwpBidSpecReview(models.TransientModel):
    """Review a project's spec: pursue it on chosen product lines, or pass with a reason.

    Either way, a side lead spotted in the spec can be parked in the pipeline Settings names.
    """

    _name = "twp.bid.spec.review"
    _description = "Review a bid / spec project"

    lead_id = fields.Many2one("crm.lead", required=True, readonly=True)
    decision = fields.Selection([("pursue", "Pursue"), ("pass", "Pass")], required=True, default="pursue")
    product_line_ids = fields.Many2many("twp.bid.spec.product.line", string="Product lines to bid")
    lost_reason_id = fields.Many2one("crm.lost.reason", string="Pass reason")
    note = fields.Text()
    side_leads_enabled = fields.Boolean(compute="_compute_side_leads_enabled")
    side_lead = fields.Boolean("Park a side lead")
    side_lead_name = fields.Char("Side lead")
    side_lead_partner_id = fields.Many2one("res.partner", string="Side lead contact")
    side_lead_note = fields.Text("Side lead note")

    @api.depends("lead_id")
    def _compute_side_leads_enabled(self):
        for review in self:
            review.side_leads_enabled = bool(review._side_lead_company().twp_bs_side_lead_team_id)

    def _side_lead_company(self):
        return self.lead_id.company_id or self.env.company

    def action_apply(self):
        self.ensure_one()
        lead = self.lead_id
        if self.decision == "pursue":
            if not self.product_line_ids:
                raise UserError(_("Pick at least one product line to bid."))
            existing = lead.twp_bs_job_ids.product_line_id
            self.env["twp.bid.spec.job"].create([
                {"lead_id": lead.id, "product_line_id": line.id}
                for line in self.product_line_ids - existing
            ])
            lead._twp_bs_move_to("bidding")
            body = _("Reviewed: pursuing %s.", ", ".join(self.product_line_ids.mapped("name")))
        else:
            if not self.lost_reason_id:
                raise UserError(_("Pick a pass reason."))
            body = _("Reviewed: passed - %s.", self.lost_reason_id.name)
        if self.note:
            body = Markup("%s<br/>%s") % (body, self.note)
        lead.message_post(body=body)
        if self.side_lead and self.side_leads_enabled:
            self._create_side_lead()
        if self.decision == "pass":
            lead.action_set_lost(lost_reason_id=self.lost_reason_id.id)
        return {"type": "ir.actions.act_window_close"}

    def _create_side_lead(self):
        if not self.side_lead_name:
            raise UserError(_("Give the side lead a name."))
        company = self._side_lead_company()
        team = company.twp_bs_side_lead_team_id
        side = self.env["crm.lead"].create({
            "name": self.side_lead_name,
            "type": "opportunity",
            "partner_id": self.side_lead_partner_id.id,
            "team_id": team.id,
            "stage_id": (company.twp_bs_side_lead_stage_id or team._twp_first_stage()).id,
            "description": self.side_lead_note,
            "twp_bs_origin_lead_id": self.lead_id.id,
        })
        self.lead_id.message_post(body=_("Side lead parked: %s", side._get_html_link()))
        return side
