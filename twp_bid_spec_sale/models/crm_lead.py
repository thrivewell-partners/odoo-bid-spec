from odoo import Command, fields, models

from odoo.addons.twp_bid_spec.models.twp_bid_spec_quote import QUOTED_AS


class CrmLead(models.Model):
    _inherit = "crm.lead"

    twp_bs_sale_order_id = fields.Many2one(
        "sale.order", string="Sales quotation", readonly=True, copy=False, index="btree_not_null",
        ondelete="set null", help="Made at Award, for the winning bid only, with a line for each job it won.")

    def action_set_lost(self, **additional_values):
        # A dead or passed project cancels any Sales quotation still open, and loses its bids.
        res = super().action_set_lost(**additional_values)
        self._twp_bs_sync_sale_order()
        return res

    def _twp_bs_winning_bids(self):
        """The bids that won this project, one per job: the buyer's, where it was sent and our
        equipment is not known to have lost."""
        self.ensure_one()
        bids = self.env["twp.bid.spec.quote"]
        for job in self.twp_bs_job_ids:
            buyer = job.bought_through_partner_id or job.awarded_partner_id
            bids |= job.quote_ids.filtered(
                lambda q: buyer and q.partner_id == buyer and q.quote_date
                and q.result not in ("lost_mfr", "project_dead"))[:1]
        return bids

    def _twp_bs_sync_sale_order(self):
        """Keep one Sales quotation per awarded project: the buyer's bid, never the others.

        Once made, the quotation belongs to Sales: awarding the same buyer again leaves it as it
        is, and a confirmed one is never touched. One still open is cancelled when the project no
        longer has a winning bid, and replaced when the award moves to another buyer. The bids
        built in Sales that did not win are marked lost.
        """
        for lead in self.filtered("twp_bs_is_bid_spec"):
            order = lead.twp_bs_sale_order_id
            is_open = order.state in ("draft", "sent")
            bids = lead._twp_bs_winning_bids()
            if not bids:
                if is_open:
                    order._action_cancel()
            elif not order or order.state == "cancel" or (is_open and order.partner_id != bids.partner_id[:1]):
                if is_open:
                    order._action_cancel()
                lead.twp_bs_sale_order_id = lead._twp_bs_new_sale_order(bids)
            if lead.twp_bs_status == "cancelled":
                losing = lead.order_ids
            elif lead.twp_bs_status == "awarded":
                losing = lead.order_ids - lead.twp_bs_sale_order_id
            else:
                continue
            losing.filtered(lambda o: o.twp_is_bid and o.twp_bid_status == "open")._twp_mark_lost()
            # A bid that won, then lost the award to another buyer, reads lost again.
            losing.filtered(lambda o: o.twp_bid_status == "won" and o.state == "cancel").twp_bid_status = "lost"

    def _twp_bs_new_sale_order(self, bids):
        """The Sales quotation for these winning bids: the bid built in Sales itself, or else one
        made from the bids as logged, a line per job."""
        self.ensure_one()
        order = bids.sale_order_id.filtered("twp_bid_number").sorted("id")[-1:]
        if order.twp_is_bid:
            order._twp_make_quotation()
        elif order.state == "cancel":
            # Won once, then the award moved away and back: the same quotation is open again.
            order.action_draft()
            order.twp_bid_status = "won"
        if order:
            return order
        lines = []
        for bid in bids:
            description = bid.job_id.product_line_id.name
            if bid.model_quoted:
                description += f" - {bid.model_quoted}"
            if bid.quoted_as:
                description += f"\n{dict(QUOTED_AS)[bid.quoted_as]}"
            lines.append(Command.create({
                "product_id": bid.job_id.product_line_id._twp_bs_sale_product().id,
                "name": description,
                "product_uom_qty": 1,
                "price_unit": bid.amount,
                # Read back by Sales margins as the bid's margin.
                "purchase_price": bid.amount * (1 - bid.margin),
            }))
        return self.env["sale.order"].create({
            "partner_id": bids.partner_id[:1].id,
            "opportunity_id": self.id,
            "team_id": self.team_id.id,
            "user_id": (bids.user_id[:1] or self.user_id).id,
            "company_id": (self.company_id or self.env.company).id,
            "origin": self.name,
            "order_line": lines,
        })
