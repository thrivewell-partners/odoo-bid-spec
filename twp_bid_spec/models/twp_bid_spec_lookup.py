from odoo import fields, models

SOURCE_KINDS = [("proactive", "Proactive"), ("inbound", "Inbound"), ("other", "Other")]
ROLE_KINDS = [
    ("contractor", "Contractor"),
    ("engineer", "Engineer"),
    ("architect", "Architect"),
    ("gc", "General contractor"),
    ("distributor", "Distributor"),
    ("manufacturer", "Manufacturer"),
    ("other", "Other"),
]


class TwpBidSpecProductLine(models.Model):
    """An equipment category the rep bids, not a line-card entry. One job is one project and one line."""

    _name = "twp.bid.spec.product.line"
    _description = "Product line"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE(name)", "A product line with this name already exists.")


class TwpBidSpecProjectType(models.Model):
    _name = "twp.bid.spec.project.type"
    _description = "Project type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE(name)", "A project type with this name already exists.")


class TwpBidSpecPartnerRole(models.Model):
    """What a contact is to the rep: contractor, engineer, manufacturer and so on. A contact can be several."""

    _name = "twp.bid.spec.partner.role"
    _description = "Contact role"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    kind = fields.Selection(
        ROLE_KINDS, required=True, default="other",
        help="What the role means to Bid / Spec. Contractors are listed on the contractor scorecard and "
             "engineers on the engineer scorecard; a contact made from a project's Architect, Engineer or "
             "GC field takes the first role of that kind; installed equipment is picked from manufacturers.",
    )
    sequence = fields.Integer(default=10)
    color = fields.Integer()

    _name_unique = models.Constraint("UNIQUE(name)", "A contact role with this name already exists.")


class TwpBidSpecSource(models.Model):
    """How a contractor bid came about. The dashboard splits outreach on the kind."""

    _name = "twp.bid.spec.source"
    _description = "Bid source"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    kind = fields.Selection(SOURCE_KINDS, required=True, default="other", string="Outreach")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE(name)", "A bid source with this name already exists.")


class TwpBidSpecHold(models.Model):
    """Why a project is waiting on something before it can be bid, shown on its card."""

    _name = "twp.bid.spec.hold"
    _description = "Project hold"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint("UNIQUE(name)", "A hold with this name already exists.")
