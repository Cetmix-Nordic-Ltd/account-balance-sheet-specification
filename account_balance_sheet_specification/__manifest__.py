# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Balance Sheet Specification",
    "summary": "Itemize the balance sheet accounts on a date, with sign-off "
    "and PDF and Excel reports",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Cetmix Nordic Ltd",
    "website": "https://github.com/Cetmix-Nordic-Ltd/account-balance-sheet-specification",
    "category": "Accounting",
    "depends": [
        "account",
        "mail",
        "report_xlsx",
    ],
    "data": [
        "security/account_balance_sheet_specification_security.xml",
        "security/ir.model.access.csv",
        "report/account_balance_sheet_specification_report.xml",
        "report/account_balance_sheet_specification_templates.xml",
        "views/account_balance_sheet_specification_line_views.xml",
        "views/account_balance_sheet_specification_views.xml",
    ],
    "demo": [
        "demo/account_balance_sheet_specification_demo.xml",
    ],
    "images": ["static/description/img/specification_form.png"],
    "installable": True,
}
