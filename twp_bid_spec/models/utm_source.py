from odoo import fields, models


class UtmSource(models.Model):
    _inherit = "utm.source"

    twp_bs_annual_cost = fields.Monetary(
        "Annual cost", currency_field="twp_bs_currency_id",
        help="What the lead service subscription costs per year, for return on subscription.")
    twp_bs_currency_id = fields.Many2one("res.currency", compute="_compute_twp_bs_currency_id")

    def _compute_twp_bs_currency_id(self):
        self.twp_bs_currency_id = self.env.company.currency_id
