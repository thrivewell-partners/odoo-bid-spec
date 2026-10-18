# odoo-bid-spec

Odoo 19 Community modules for tracking bid / spec work in CRM. A distributor or manufacturer's
rep follows a project from its spec to the award: which contractors it bid to on each product
line, what each bid was, who won, and whose equipment went in. Off until each client's admin turns
it on in Settings > CRM > Bid / Spec, where it is also set up. Radiant Energy Distribution is the
first client.

| Module | Status | What it does |
|---|---|---|
| `twp_stage_requirements` | Built, 19.0.1.0.0 | Each CRM stage can list the fields a card needs there, with a warning shown on the card while one is empty, and stamp a date when a card first reaches it |
| `twp_bid_spec` | Built, 19.0.1.1.0 | Bid / Spec projects, jobs (one project and one product line), contractor bids, the result of each bid, review, award, follow-ups, the dashboard and scorecards |
| `twp_bid_spec_sale` | Planned (M2) | Bids built in Sales fill the contractor bids, and Award turns the winning bid into the quotation. Depends on `twp_bids` from `odoo-advanced-quoting` |

This repo is the master copy. Releases are copied into each client's code repo, which is that
client's addons path on Oduflow.

The plan lives in ThriveWell's tree at `thrivewell/work/design/2026-10-18-bid-spec-module-plan.md`.
