from odoo import fields, models


class TwpStageRequirement(models.Model):
    """One field a card needs while it is in a stage, and the warning shown until it is filled in."""

    _name = "twp.stage.requirement"
    _description = "Stage requirement"
    _order = "stage_id, sequence, id"

    stage_id = fields.Many2one("crm.stage", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",
        domain=[("model", "=", "crm.lead"), ("ttype", "!=", "binary")],
        help="The card's field that must not be empty.",
    )
    # Stored, so reading a card's warning needs no access to the field definitions.
    field_name = fields.Char(related="field_id.name", store=True)
    message = fields.Char(
        string="Warning", required=True, translate=True, help="Shown on the card while the field is empty."
    )
