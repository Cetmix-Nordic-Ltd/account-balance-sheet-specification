# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, time

from odoo import fields, models


class AccountBalanceSheetSpecificationLine(models.Model):
    _inherit = "account.balance.sheet.specification.line"

    method = fields.Selection(
        selection_add=[("inventory", "Inventory valuation")],
        ondelete={"inventory": "set default"},
    )


class AccountBalanceSheetSpecification(models.Model):
    _inherit = "account.balance.sheet.specification"

    def _get_auto_items(self, accounts):
        result = super()._get_auto_items(accounts)
        categories = (
            self.env["product.category"].with_company(self.company_id).search([])
        )
        by_account = {}
        for category in categories:
            account = category.property_stock_valuation_account_id
            if account in accounts and account.id not in result:
                by_account.setdefault(account, self.env["product.category"])
                by_account[account] |= category
        for account, account_categories in by_account.items():
            items = self._get_inventory_items(account_categories)
            if items:
                result[account.id] = ("inventory", items)
        return result

    def _get_inventory_items(self, categories):
        """Stock value on the date per product category, from the stock
        valuation layers created by the end of the day."""
        self.ensure_one()
        groups = self.env["stock.valuation.layer"]._read_group(
            [
                ("company_id", "=", self.company_id.id),
                ("categ_id", "in", categories.ids),
                ("create_date", "<=", datetime.combine(self.date, time.max)),
            ],
            groupby=["categ_id"],
            aggregates=["value:sum", "quantity:sum"],
        )
        items = []
        for category, value, quantity in sorted(
            groups, key=lambda g: g[0].complete_name or ""
        ):
            if self.currency_id.is_zero(value):
                continue
            items.append(
                {
                    "name": self.env._(
                        "%(category)s: stock value (%(quantity)s units)",
                        category=category.complete_name,
                        quantity=round(quantity, 2),
                    ),
                    "amount": value,
                    "res_model": category._name,
                    "res_id": category.id,
                }
            )
        return items
