# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountBalanceSheetSpecificationLine(models.Model):
    """One balance sheet account of a specification."""

    _name = "account.balance.sheet.specification.line"
    _description = "Balance Sheet Specification Account"
    _order = "sequence, id"
    _rec_name = "account_id"

    specification_id = fields.Many2one(
        comodel_name="account.balance.sheet.specification",
        required=True,
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(related="specification_id.state")
    company_id = fields.Many2one(related="specification_id.company_id", store=True)
    currency_id = fields.Many2one(related="specification_id.currency_id")
    sequence = fields.Integer()
    group_name = fields.Char(string="Balance Sheet Item", readonly=True)
    account_id = fields.Many2one(
        comodel_name="account.account", required=True, readonly=True, index=True
    )
    balance = fields.Monetary(readonly=True)
    method = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("open_items", "Open items"),
            ("bank_statement", "Bank statement"),
        ],
        default="manual",
        required=True,
        readonly=True,
        help="How Odoo itemized the balance; Manual: the items are typed by " "hand.",
    )
    item_ids = fields.One2many(
        comodel_name="account.balance.sheet.specification.item",
        inverse_name="line_id",
        string="Items",
    )
    auto_amount = fields.Monetary(
        string="Itemized by Odoo", compute="_compute_amounts", store=True
    )
    manual_amount = fields.Monetary(
        string="Itemized by Hand", compute="_compute_amounts", store=True
    )
    difference = fields.Monetary(
        string="Unexplained",
        compute="_compute_amounts",
        store=True,
        help="Balance less the items: what is not yet explained.",
    )
    note = fields.Text()
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="account_bs_specification_line_attachment_rel",
        column1="line_id",
        column2="attachment_id",
        string="Attachments",
    )

    _sql_constraints = [
        (
            "account_unique",
            "unique(specification_id, account_id)",
            "An account is only once in a specification.",
        )
    ]

    @api.depends("balance", "item_ids.amount", "item_ids.kind")
    def _compute_amounts(self):
        for line in self:
            items = line.item_ids
            line.auto_amount = sum(
                items.filtered(lambda i: i.kind == "auto").mapped("amount")
            )
            line.manual_amount = sum(
                items.filtered(lambda i: i.kind == "manual").mapped("amount")
            )
            line.difference = line.currency_id.round(
                line.balance - line.auto_amount - line.manual_amount
            )

    def write(self, vals):
        if set(vals) & {"note", "attachment_ids"}:
            self.specification_id._check_draft()
        return super().write(vals)

    def _has_manual_content(self):
        self.ensure_one()
        return bool(
            self.note
            or self.attachment_ids
            or self.item_ids.filtered(lambda i: i.kind == "manual")
        )

    def _copy_from_previous(self, previous):
        """Start the manual items and the note of new lines from the same
        account in ``previous``; the items are marked as copied."""
        previous_lines = {line.account_id: line for line in previous.line_ids}
        Item = self.env["account.balance.sheet.specification.item"]
        for line in self:
            old = previous_lines.get(line.account_id)
            if not old:
                continue
            if old.note and not line.note:
                line.note = old.note
            Item.create(
                [
                    {
                        "line_id": line.id,
                        "kind": "manual",
                        "name": item.name,
                        "partner_id": item.partner_id.id,
                        "reference": item.reference,
                        "amount": item.amount,
                        "copied": True,
                    }
                    for item in old.item_ids.filtered(lambda i: i.kind == "manual")
                ]
            )

    def action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_move_lines(self):
        self.ensure_one()
        spec = self.specification_id
        return {
            "type": "ir.actions.act_window",
            "name": self.account_id.display_name,
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": spec._move_line_domain()
            + [("account_id", "=", self.account_id.id)],
            "context": {"search_default_group_by_partner": 1},
        }
