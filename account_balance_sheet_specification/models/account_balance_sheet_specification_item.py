# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountBalanceSheetSpecificationItem(models.Model):
    """An item that explains part of an account's balance: computed by
    Odoo (open items of a partner, a bank statement, an asset...) or typed
    by hand (a loan, an accrual...)."""

    _name = "account.balance.sheet.specification.item"
    _description = "Balance Sheet Specification Item"
    _order = "kind, sequence, id"

    line_id = fields.Many2one(
        comodel_name="account.balance.sheet.specification.line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    specification_id = fields.Many2one(
        related="line_id.specification_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="line_id.currency_id")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        selection=[("auto", "By Odoo"), ("manual", "By hand")],
        default="manual",
        required=True,
    )
    name = fields.Char(string="Description", required=True)
    partner_id = fields.Many2one(comodel_name="res.partner")
    date = fields.Date()
    reference = fields.Char()
    amount = fields.Monetary(required=True)
    copied = fields.Boolean(
        string="From Previous",
        help="Copied from the previous specification: check and update it.",
    )
    res_model = fields.Char(string="Source Model", readonly=True)
    res_id = fields.Many2oneReference(
        string="Source ID", model_field="res_model", readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        items = super().create(vals_list)
        items.filtered(lambda i: i.kind == "manual").specification_id._check_draft()
        return items

    def write(self, vals):
        self.specification_id._check_draft()
        if "amount" in vals or "name" in vals:
            vals.setdefault("copied", False)
        return super().write(vals)

    def unlink(self):
        self.filtered(lambda i: i.kind == "manual").specification_id._check_draft()
        return super().unlink()

    def action_open_source(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        record = self.env[self.res_model].browse(self.res_id).exists()
        return record.get_formview_action() if record else False
