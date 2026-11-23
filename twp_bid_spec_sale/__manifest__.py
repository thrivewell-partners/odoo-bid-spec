{
    "name": "Bid / Spec: bids in Sales",
    "summary": "Bids built in Sales fill the Bid / Spec contractor bids, and Award turns the winning bid into the quotation",
    "description": """
Ties Bids to Bid / Spec. A bid built in Sales on a Bid / Spec project fills that project's
contractor bids, one per product line it carries, with the amount, margin and model, and sending it
stamps Bid sent and books the follow-up, as Log bid does. Award turns the winning bid into the
project's Sales quotation and marks the other bids lost; a bid logged by hand gets a quotation made
for it. A project cancelled or postponed loses every open bid. On a Bid / Spec bid, Won opens Award.

Bids belong to Bid / Spec: New Bid shows only on a Bid / Spec card, Sales' Bids list moves to CRM >
Bids as Bid documents, and every other opportunity keeps Sales' own New Quotation.

The amount read from a bid is what its total counts, so alternatives and add-ons not chosen stay
out of it. Each product line has a Sales product of its own, so a bid can be built before the
catalog is loaded, and catalog products can name the product line they belong to. A product that names none, such as an
accessory, follows the product line of its bundle when the bundle's products name just one; in a
bundle of two lines, in a bundle naming none, or outside any bundle, it counts toward no job and the
bid lists it as unmatched.
""",
    "version": "19.0.1.4.0",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "author": "ThriveWell Partners",
    "depends": ["twp_bid_spec", "twp_bids"],
    "data": [
        "views/sale_order_views.xml",
        "views/crm_lead_views.xml",
        "views/twp_bid_spec_views.xml",
        "views/product_views.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "auto_install": True,
    "installable": True,
}
