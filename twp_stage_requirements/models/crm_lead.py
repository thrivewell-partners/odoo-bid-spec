from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    twp_needs_attention = fields.Char(
        string="Needs attention", compute="_compute_twp_needs_attention",
        help="What the card still lacks: the first missing requirement of its stage.",
    )

    @api.model
    def _twp_attention_depends(self):
        """The fields a card's warning reads. Extend it in modules that add warnings of their own.

        A stage's requirements are data, so they cannot be listed here; `write` refreshes the
        warning instead.
        """
        return ["active", "won_status", "stage_id", "stage_id.twp_requirement_ids.field_name"]

    @api.depends(lambda self: self._twp_attention_depends())
    def _compute_twp_needs_attention(self):
        for lead in self:
            lead.twp_needs_attention = lead._twp_attention()

    def _twp_attention(self):
        """The warning for one card, or False. Modules add their own ahead of the stage's."""
        self.ensure_one()
        if not self.active or self.won_status != "pending":
            return False
        for requirement in self.stage_id.twp_requirement_ids:
            name = requirement.field_name
            if name in self._fields and not self[name]:
                return requirement.message
        return False

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._twp_stamp_stage_dates()
        return leads

    def write(self, vals):
        res = super().write(vals)
        if "stage_id" in vals:
            self._twp_stamp_stage_dates()
        # Any field can be a requirement, so any write may change the warning.
        self.invalidate_recordset(["twp_needs_attention"])
        return res

    def _twp_stamp_stage_dates(self):
        for stage, leads in self.grouped("stage_id").items():
            field = stage.twp_stamp_field_id
            if not field or field.name not in self._fields:
                continue
            unstamped = leads.filtered(lambda lead: not lead[field.name])
            if unstamped:
                now = fields.Datetime.now() if field.ttype == "datetime" else fields.Date.context_today(self)
                unstamped.write({field.name: now})
