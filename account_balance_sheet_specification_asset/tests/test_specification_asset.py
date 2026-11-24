# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSpecificationAsset(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.asset_account = cls.env["account.account"].create(
            {
                "code": "112000",
                "name": "Machinery",
                "account_type": "asset_fixed",
                "company_ids": [Command.set(cls.company.ids)],
            }
        )
        cls.profile = cls.env["account.asset.profile"].create(
            {
                "name": "Machinery - 5 years",
                "account_asset_id": cls.asset_account.id,
                "account_depreciation_id": cls.asset_account.id,
                "account_expense_depreciation_id": cls.company_data[
                    "default_account_expense"
                ].id,
                "journal_id": cls.company_data["default_journal_misc"].id,
                "method_time": "year",
                "method_number": 5,
                "method_period": "year",
            }
        )
        cls.other = cls.company_data["default_account_revenue"]

    def _entry(self, day, lines, **ctx):
        move = (
            self.env["account.move"]
            .with_context(**ctx)
            .create(
                {
                    "move_type": "entry",
                    "date": day,
                    "journal_id": self.company_data["default_journal_misc"].id,
                    "line_ids": [Command.create(values) for values in lines],
                }
            )
        )
        move.action_post()
        return move

    def test_items_per_asset(self):
        purchase = self._entry(
            date(2025, 3, 1),
            [
                {
                    "account_id": self.asset_account.id,
                    "asset_profile_id": self.profile.id,
                    "name": "Lathe",
                    "debit": 1200.0,
                },
                {"account_id": self.other.id, "name": "x", "credit": 1200.0},
            ],
        )
        asset = purchase.line_ids.asset_id
        self.assertTrue(asset)
        # Depreciation booked against the asset, and a posting without asset
        self._entry(
            date(2025, 12, 31),
            [
                {
                    "account_id": self.asset_account.id,
                    "asset_id": asset.id,
                    "name": "Depreciation",
                    "credit": 300.0,
                },
                {"account_id": self.other.id, "name": "x", "debit": 300.0},
            ],
            allow_asset=True,
            skip_asset_creation_on_post=True,
        )
        self._entry(
            date(2025, 12, 31),
            [
                {"account_id": self.asset_account.id, "name": "Unknown", "debit": 50.0},
                {"account_id": self.other.id, "name": "x", "credit": 50.0},
            ],
            skip_asset_creation_on_post=True,
        )
        spec = self.env["account.balance.sheet.specification"].create(
            {"name": "2025", "date": date(2025, 12, 31), "company_id": self.company.id}
        )
        spec.action_compute()
        line = spec.line_ids.filtered(
            lambda line: line.account_id == self.asset_account
        )
        self.assertEqual(line.method, "assets")
        self.assertEqual(line.balance, 950.0)
        self.assertEqual(line.item_ids.res_id, asset.id)
        self.assertEqual(line.item_ids.amount, 900.0)
        self.assertEqual(line.difference, 50.0)
