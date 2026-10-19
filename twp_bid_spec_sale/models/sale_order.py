from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.twp_bid_spec.models.twp_bid_spec_quote import QUOTED_AS

# A change to any of these moves a bid's figures on its project.
SYNC_FIELDS = {"order_line", "partner_id", "opportunity_id", "user_id", "twp_bs_quoted_as", "twp_bs_source_id"}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    twp_bs_is_bid_spec = fields.Boolean(related="opportunity_id.twp_bs_is_bid_spec", string="Is Bid / Spec")
    twp_bs_quoted_as = fields.Selection(QUOTED_AS, string="Bid as")
    twp_bs_source_id = fields.Many2one("twp.bid.spec.source", string="Bid source")
    twp_bs_unmatched_lines = fields.Text(
        compute="_compute_twp_bs_unmatched_lines",
        help="Lines that count toward no job, because neither their product nor the project says which.")

    @api.depends("order_line.product_id", "order_line.display_type", "opportunity_id.twp_bs_job_ids", "twp_is_bid")
    def _compute_twp_bs_unmatched_lines(self):
        for order in self:
            unmatched = order._twp_bs_lines_by_product_line()[1] if order.twp_is_bid and order.twp_bs_is_bid_spec else []
            order.twp_bs_unmatched_lines = "\n".join(
                f"- {(line.name or line.product_id.display_name).splitlines()[0]}" for line in unmatched) or False

    def _twp_bs_lines_by_product_line(self):
        """({product line: lines}, lines matched to none). A line counts toward its product's
        product line, else toward the project's only job. Lines kept out of the total, such as an
        alternative not chosen, count toward nothing."""
        self.ensure_one()
        jobs = self.opportunity_id.twp_bs_job_ids
        only = jobs.product_line_id if len(jobs) == 1 else self.env["twp.bid.spec.product.line"]
        self.order_line._twp_refresh_parents()
        groups, unmatched = {}, self.env["sale.order.line"]
        for line in self.order_line.sorted("sequence"):
            if line.display_type or line._twp_is_special() or line._twp_is_excluded():
                continue
            product_line = line.product_id.product_tmpl_id.twp_bs_product_line_id or only
            if product_line:
                groups[product_line] = groups.get(product_line, self.env["sale.order.line"]) | line
            else:
                unmatched |= line
        return groups, unmatched

    def _twp_bs_model_quoted(self, lines):
        """What the bid offers on a job, from its first line: the product, or what the rep typed."""
        line = lines[:1]
        generic = line.product_id.product_tmpl_id.twp_bs_product_line_id.product_id
        if line.product_id and line.product_id != generic:
            return line.product_id.display_name
        return ((line.name or "").splitlines() or [""])[0][:80] or False

    def _twp_bs_sync_bid_lines(self):
        """Each open Bid / Spec bid fills one contractor bid per product line it carries."""
        Quote = self.env["twp.bid.spec.quote"]
        Job = self.env["twp.bid.spec.job"]
        today = fields.Date.context_today(self)
        for order in self.filtered(lambda o: o.twp_is_bid and o.twp_bs_is_bid_spec):
            linked = Quote.search([("sale_order_id", "=", order.id)])
            rows = Quote
            if order.partner_id:
                lead = order.opportunity_id
                for product_line, lines in order._twp_bs_lines_by_product_line()[0].items():
                    job = lead.twp_bs_job_ids.filtered(lambda j: j.product_line_id == product_line)[:1] or Job.create(
                        {"lead_id": lead.id, "product_line_id": product_line.id})
                    row = job.quote_ids.filtered(lambda q: q.partner_id == order.partner_id)[:1]
                    amount = sum(lines.mapped("price_subtotal"))
                    vals = {
                        "sale_order_id": order.id,
                        "amount": amount,
                        "margin": sum(lines.mapped("margin")) / amount if amount else 0.0,
                        "model_quoted": order._twp_bs_model_quoted(lines),
                        "user_id": (order.user_id or row.user_id).id,
                    }
                    if order.twp_bs_quoted_as:
                        vals["quoted_as"] = order.twp_bs_quoted_as
                    if order.twp_bs_source_id:
                        vals["source_id"] = order.twp_bs_source_id.id
                    if order.twp_bid_sent_date and not row.quote_date:
                        vals.update(quote_date=order.twp_bid_sent_date, last_contact_date=order.twp_bid_sent_date)
                    if row:
                        row.write(vals)
                    else:
                        row = Quote.create({
                            "job_id": job.id, "partner_id": order.partner_id.id, "first_contact_date": today, **vals})
                    rows |= row
            # A job dropped from the bid, or another bidder chosen: those bids no longer come from it.
            (linked - rows).write({"sale_order_id": False})

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._twp_bs_sync_bid_lines()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if SYNC_FIELDS & vals.keys():
            self._twp_bs_sync_bid_lines()
        return result

    def _twp_bid_sent(self):
        super()._twp_bid_sent()
        bids = self.filtered(lambda o: o.twp_is_bid and o.twp_bs_is_bid_spec)
        bids._twp_bs_sync_bid_lines()
        today = fields.Date.context_today(self)
        for row in self.env["twp.bid.spec.quote"].search([("sale_order_id", "in", bids.ids)]):
            days = (row.company_id or self.env.company).twp_bs_followup_days
            row._twp_bs_touch(
                _("Bid %(bid)s sent: %(amount)s", bid=row.sale_order_id.name, amount=row.currency_id.format(row.amount)),
                next_date=today + timedelta(days=days))

    def action_twp_bid_won(self):
        # On Bid / Spec, a bid is won through the project's Award, which also records the jobs.
        bid_spec = self.filtered("twp_bs_is_bid_spec")
        if len(self) == 1 and bid_spec:
            action = self.opportunity_id.action_twp_bs_award()
            action["context"] = {**action["context"], "default_awarded_partner_id": self.partner_id.id}
            return action
        return super(SaleOrder, self - bid_spec).action_twp_bid_won()
