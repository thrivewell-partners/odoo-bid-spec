from odoo import Command, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    twp_bs_role_ids = fields.Many2many(
        "twp.bid.spec.partner.role", "twp_bs_partner_role_rel", "partner_id", "role_id", string="Roles")
    # RESULT reads it to decide a job was won.
    twp_bs_we_represent = fields.Boolean(
        "We represent", help="We represent this manufacturer. An install of their equipment counts as a win.")
    twp_bs_product_line_ids = fields.Many2many(
        "twp.bid.spec.product.line", "twp_bs_partner_product_line_rel", "partner_id", "product_line_id",
        string="Product lines", help="The product lines this manufacturer covers.")

    @api.model
    def default_get(self, fields_list):
        # A contact made from a project's Engineer field, say, starts with the first Engineer role.
        res = super().default_get(fields_list)
        kind = self.env.context.get("twp_bs_role_kind")
        if kind and "twp_bs_role_ids" in fields_list and not res.get("twp_bs_role_ids"):
            role = self.env["twp.bid.spec.partner.role"].search([("kind", "=", kind)], limit=1)
            if role:
                res["twp_bs_role_ids"] = [Command.set(role.ids)]
        return res
