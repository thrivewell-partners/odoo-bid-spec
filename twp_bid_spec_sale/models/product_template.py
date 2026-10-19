from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    twp_bs_product_line_id = fields.Many2one(
        "twp.bid.spec.product.line", string="Bid / Spec product line", index="btree_not_null",
        help="The product line this product is bid under. On a Bid / Spec bid, its lines count toward that job.")
