from odoo import api, fields, models


class TwpBidSpecProductLine(models.Model):
    _inherit = "twp.bid.spec.product.line"

    product_id = fields.Many2one(
        "product.product", string="Sales product", ondelete="restrict",
        help="What this line is sold as on a bid or an awarded quotation when no catalog product says more.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            line._twp_bs_sale_product()
        return lines

    def _twp_bs_sale_product(self):
        self.ensure_one()
        if not self.product_id:
            # Sudo: the rep awarding the job may not be allowed to create products.
            self.sudo().product_id = self.env["product.product"].sudo().create({
                "name": self.name, "type": "consu", "twp_bs_product_line_id": self.id})
        return self.product_id
