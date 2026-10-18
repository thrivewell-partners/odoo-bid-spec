from odoo import fields, models


class CrmStage(models.Model):
    _inherit = "crm.stage"

    twp_requirement_ids = fields.One2many(
        "twp.stage.requirement", "stage_id", string="Needs", copy=True,
        help="What a card needs while it is in this stage. The first one missing is shown on the card.",
    )
    twp_stamp_field_id = fields.Many2one(
        "ir.model.fields",
        string="On arrival, stamp",
        ondelete="set null",
        domain=[("model", "=", "crm.lead"), ("ttype", "in", ("date", "datetime"))],
        help="A date filled with today when a card first reaches this stage. One already filled in is kept.",
    )
