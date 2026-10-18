from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = "crm.team"

    twp_bs_enabled = fields.Boolean(
        string="Bid / Spec",
        help="This pipeline tracks bid / spec projects: jobs, contractor bids, review and award.",
    )

    def _twp_bs_stage(self, step):
        """This pipeline's first stage at a Bid / Spec step, or an empty recordset."""
        self.ensure_one()
        return self.env["crm.stage"].search([
            ("twp_bs_step", "=", step),
            "|", ("team_ids", "=", False), ("team_ids", "in", self.ids),
        ], order="sequence, id", limit=1)

    def _twp_first_stage(self):
        """Where a new card in this pipeline starts."""
        self.ensure_one()
        return self.env["crm.stage"].search(
            ["|", ("team_ids", "=", False), ("team_ids", "in", self.ids)], order="sequence, id", limit=1)
