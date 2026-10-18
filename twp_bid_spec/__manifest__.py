{
    "name": "Bid / Spec",
    "summary": "Bid / spec projects in CRM: jobs, contractor bids, review, award, follow-ups and reports",
    "description": """
For a manufacturer's rep or distributor bidding equipment into specified projects. On a pipeline
ticked Bid / Spec, an opportunity is a project: a job for each product line, each contractor's
bid on each job, and the result of every bid once the project is awarded. Review pursues or
passes a project, Log bid and Log a touch book the follow-ups, Award names the winner and whose
equipment went in. A follow-up queue, a dashboard for any window, and contractor and engineer
scorecards. Configured in Settings > CRM > Bid / Spec.
""",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "author": "ThriveWell Partners",
    "depends": ["twp_stage_requirements", "contacts", "utm", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/twp_bid_spec_data.xml",
        "data/ir_cron_data.xml",
        "views/crm_lead_views.xml",
        "views/crm_team_stage_views.xml",
        "views/twp_bid_spec_quote_views.xml",
        "views/twp_bid_spec_job_views.xml",
        "views/res_partner_views.xml",
        "views/twp_bid_spec_config_views.xml",
        "views/twp_bid_spec_followup_views.xml",
        "views/twp_bid_spec_report_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/twp_bid_spec_wizard_views.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
