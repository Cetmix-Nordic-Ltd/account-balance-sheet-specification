# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSpecificationStock(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.stock_account = cls.env["account.account"].create(
            {
                "code": "150000",
                "name": "Raw materials",
                "account_type": "asset_current",
                "company_ids": [Command.set(cls.company.ids)],
            }
        )
        cls.category = (
            cls.env["product.category"]
            .with_company(cls.company)
            .create(
                {
                    "name": "Steel",
                    "property_cost_method": "standard",
                    "property_valuation": "manual_periodic",
                    "property_stock_valuation_account_id": cls.stock_account.id,
                }
            )
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Steel bar",
                "is_storable": True,
                "categ_id": cls.category.id,
                "standard_price": 10.0,
            }
        )

    def test_inventory_items(self):
        today = fields.Date.context_today(self.env.user)
        Layer = self.env["stock.valuation.layer"].with_company(self.company)
        for quantity in (30.0, 20.0):
            Layer.create(
                {
                    "company_id": self.company.id,
                    "product_id": self.product.id,
                    "quantity": quantity,
                    "unit_cost": 10.0,
                    "value": quantity * 10.0,
                }
            )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": today,
                "line_ids": [
                    Command.create(
                        {"account_id": self.stock_account.id, "debit": 500.0}
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "credit": 500.0,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        spec = self.env["account.balance.sheet.specification"].create(
            {"name": "Now", "date": today, "company_id": self.company.id}
        )
        spec.action_compute()
        line = spec.line_ids.filtered(
            lambda line: line.account_id == self.stock_account
        )
        self.assertEqual(line.method, "inventory")
        self.assertEqual(line.item_ids.amount, 500.0)
        self.assertIn("Steel", line.item_ids.name)
        self.assertEqual(line.difference, 0.0)
