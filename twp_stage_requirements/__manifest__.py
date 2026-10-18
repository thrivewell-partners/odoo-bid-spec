{
    "name": "Stage Requirements",
    "summary": "Each CRM stage lists what a card needs there, and can stamp a date on arrival",
    "description": """
A stage can list the fields a card needs while it sits there, each with the warning to show until
the field is filled in. The card shows the first unmet one, on the board and at the top of its
form. A stage can also name a date field to fill with today when a card first reaches it.
Configured on each stage, under CRM > Configuration > Stages.
""",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "license": "LGPL-3",
    "author": "ThriveWell Partners",
    "depends": ["crm"],
    "data": [
        "security/ir.model.access.csv",
        "views/crm_stage_views.xml",
        "views/crm_lead_views.xml",
    ],
    "installable": True,
}
