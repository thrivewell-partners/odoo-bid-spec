from markupsafe import Markup

from odoo import Command, _, api, fields, models


class TwpBidSpecAward(models.TransientModel):
    """Record who won the project, who they buy through, and whose equipment went in on each job,
    and move the project to Awarded.

    One contractor wins the whole project. When they buy the equipment through a distributor we
    bid to, the distributor's bid is the win. Leave a line's installed manufacturer empty when it
    is not known yet: its bids read "Awarded - Update" until it is filled in.
    """

    _name = "twp.bid.spec.award"
    _description = "Award a bid / spec project"

    lead_id = fields.Many2one("crm.lead", required=True, readonly=True)
    awarded_partner_id = fields.Many2one("res.partner", string="Awarded to", help="The contractor who won the project.")
    bought_through_partner_id = fields.Many2one(
        "res.partner", string="Bought through",
        help="The distributor the contractor buys the equipment through, when it is one we bid to.")
    quoted_partner_ids = fields.Many2many("res.partner", string="We bid to", compute="_compute_quoted_partner_ids")
    line_ids = fields.One2many("twp.bid.spec.award.line", "award_id")

    @api.depends("lead_id")
    def _compute_quoted_partner_ids(self):
        for award in self:
            award.quoted_partner_ids = award.lead_id.twp_bs_quote_ids.partner_id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead = self.env["crm.lead"].browse(res.get("lead_id") or self.env.context.get("active_id"))
        if lead:
            jobs = lead.twp_bs_job_ids
            # An award already made reads back; otherwise a winner passed in the context stays.
            if "awarded_partner_id" in fields_list and jobs.awarded_partner_id:
                res["awarded_partner_id"] = jobs.awarded_partner_id[:1].id
            if "bought_through_partner_id" in fields_list and jobs.bought_through_partner_id:
                res["bought_through_partner_id"] = jobs.bought_through_partner_id[:1].id
            if "line_ids" in fields_list:
                res["line_ids"] = [Command.create({
                    "job_id": job.id,
                    "installed_partner_id": job.installed_partner_id.id,
                }) for job in jobs]
        return res

    def action_apply(self):
        self.ensure_one()
        lead = self.lead_id
        for line in self.line_ids:
            line.job_id.write({
                "awarded_partner_id": self.awarded_partner_id.id,
                "bought_through_partner_id": self.bought_through_partner_id.id,
                "installed_partner_id": line.installed_partner_id.id,
            })
        if lead.twp_bs_status != "awarded":
            lead._twp_bs_move_to("awarded")
        # After the stage: a bid only reads as won or lost once its project is Awarded.
        self._twp_bs_after_award()
        lines = Markup("").join(
            Markup("<li>%s: %s</li>") % (
                line.job_id.product_line_id.name, line.installed_partner_id.name or _("equipment not known"))
            for line in self.line_ids)
        lead.message_post(body=Markup("%s<ul>%s</ul>") % (_("Awarded to %s.", self._twp_bs_winner_label()), lines))
        return {"type": "ir.actions.act_window_close"}

    def _twp_bs_after_award(self):
        """What else follows the award, once the jobs and the stage are written."""

    def _twp_bs_winner_label(self):
        winner = self.awarded_partner_id.name or _("contractor not known")
        if self.bought_through_partner_id:
            winner = _("%(contractor)s, through %(distributor)s",
                       contractor=winner, distributor=self.bought_through_partner_id.name)
        return winner


class TwpBidSpecAwardLine(models.TransientModel):
    _name = "twp.bid.spec.award.line"
    _description = "Award line"

    award_id = fields.Many2one("twp.bid.spec.award", required=True, ondelete="cascade")
    job_id = fields.Many2one("twp.bid.spec.job", required=True)
    product_line_id = fields.Many2one(related="job_id.product_line_id")
    quoted_partner_ids = fields.Many2many("res.partner", string="We bid to", compute="_compute_quoted_partner_ids")
    installed_partner_id = fields.Many2one("res.partner", string="Installed mfr")

    @api.depends("job_id")
    def _compute_quoted_partner_ids(self):
        for line in self:
            line.quoted_partner_ids = line.job_id.quote_ids.partner_id
