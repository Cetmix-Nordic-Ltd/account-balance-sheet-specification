# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountBalanceSheetSpecificationLine(models.Model):
    _inherit = "account.balance.sheet.specification.line"

    method = fields.Selection(
        selection_add=[("assets", "Assets")], ondelete={"assets": "set default"}
    )


class AccountBalanceSheetSpecification(models.Model):
    _inherit = "account.balance.sheet.specification"

    def _get_auto_items(self, accounts):
        result = super()._get_auto_items(accounts)
        profiles = self.env["account.asset.profile"].search(
            [("company_id", "=", self.company_id.id)]
        )
        asset_accounts = (
            profiles.account_asset_id | profiles.account_depreciation_id
        ).filtered(lambda a: a in accounts and a.id not in result)
        result.update(self._get_asset_items(asset_accounts))
        return result

    def _get_asset_items(self, accounts):
        """The balance of each asset on the account: acquisition less the
        depreciation booked by the date, from the journal items linked to
        the asset."""
        self.ensure_one()
        if not accounts:
            return {}
        groups = self.env["account.move.line"]._read_group(
            self._move_line_domain()
            + [("account_id", "in", accounts.ids), ("asset_id", "!=", False)],
            groupby=["account_id", "asset_id"],
            aggregates=["balance:sum"],
        )
        result = {}
        for account, asset, balance in sorted(
            groups, key=lambda g: (g[1].code or "", g[1].name or "")
        ):
            if self.currency_id.is_zero(balance):
                continue
            items = result.setdefault(account.id, ("assets", []))[1]
            items.append(
                {
                    "name": asset.display_name,
                    "reference": asset.code or False,
                    "date": asset.date_start,
                    "partner_id": asset.partner_id.id,
                    "amount": balance,
                    "res_model": asset._name,
                    "res_id": asset.id,
                }
            )
        return result
