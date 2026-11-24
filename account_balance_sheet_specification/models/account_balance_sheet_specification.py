# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

# Account types that are not on the balance sheet
PROFIT_AND_LOSS_TYPES = (
    "income",
    "income_other",
    "expense",
    "expense_depreciation",
    "expense_direct_cost",
)
NOT_BALANCE_SHEET_TYPES = PROFIT_AND_LOSS_TYPES + ("off_balance",)


class AccountBalanceSheetSpecification(models.Model):
    """Specification of the balance sheet on a date: every balance sheet
    account with its balance and the items that make it up."""

    _name = "account.balance.sheet.specification"
    _description = "Balance Sheet Specification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    date = fields.Date(
        required=True,
        tracking=True,
        default=lambda self: self._default_date(),
        help="The balances are those at the end of this day, posted entries " "only.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("prepared", "Prepared"),
            ("checked", "Checked"),
        ],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    line_ids = fields.One2many(
        comodel_name="account.balance.sheet.specification.line",
        inverse_name="specification_id",
        string="Accounts",
        copy=False,
    )
    computed_date = fields.Datetime(string="Computed On", readonly=True, copy=False)
    prepared_by_id = fields.Many2one(
        comodel_name="res.users", string="Prepared By", readonly=True, copy=False
    )
    prepared_date = fields.Datetime(string="Prepared On", readonly=True, copy=False)
    checked_by_id = fields.Many2one(
        comodel_name="res.users", string="Checked By", readonly=True, copy=False
    )
    checked_date = fields.Datetime(string="Checked On", readonly=True, copy=False)
    note = fields.Html()
    total_assets = fields.Monetary(readonly=True, copy=False)
    total_liabilities = fields.Monetary(readonly=True, copy=False)
    total_equity = fields.Monetary(readonly=True, copy=False)
    unallocated_earnings = fields.Monetary(
        readonly=True,
        copy=False,
        help="Profit or loss not yet closed to equity: the opposite of the "
        "balance of all income and expense accounts up to the date.",
    )
    balance_difference = fields.Monetary(
        compute="_compute_summary",
        help="Assets less liabilities, equity and unallocated earnings. Zero "
        "when the books balance.",
    )
    unexplained_count = fields.Integer(
        string="Unexplained Accounts", compute="_compute_summary"
    )
    previous_id = fields.Many2one(
        comodel_name="account.balance.sheet.specification",
        string="Previous Specification",
        compute="_compute_previous_id",
    )

    @api.model
    def _default_date(self):
        today = fields.Date.context_today(self)
        return self.env.company.compute_fiscalyear_dates(today)["date_to"]

    @api.onchange("date")
    def _onchange_date(self):
        if self.date and not self.name:
            self.name = self.env._(
                "Balance sheet specification %(date)s", date=self.date
            )

    @api.depends(
        "total_assets",
        "total_liabilities",
        "total_equity",
        "unallocated_earnings",
        "line_ids.difference",
    )
    def _compute_summary(self):
        for spec in self:
            spec.balance_difference = (
                spec.total_assets
                - spec.total_liabilities
                - spec.total_equity
                - spec.unallocated_earnings
            )
            currency = spec.currency_id
            spec.unexplained_count = sum(
                1 for line in spec.line_ids if not currency.is_zero(line.difference)
            )

    @api.depends("date", "company_id")
    def _compute_previous_id(self):
        for spec in self:
            spec.previous_id = (
                self.search(
                    [
                        ("company_id", "=", spec.company_id.id),
                        ("date", "<", spec.date),
                        ("id", "!=", spec._origin.id),
                    ],
                    order="date desc, id desc",
                    limit=1,
                )
                if spec.date
                else False
            )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _check_draft(self):
        if any(spec.state != "draft" for spec in self):
            raise UserError(
                self.env._(
                    "A prepared or checked specification cannot be changed. "
                    "Reset it to draft first."
                )
            )

    def action_compute(self):
        self._check_draft()
        for spec in self:
            spec._compute_lines()
        return True

    def action_prepare(self):
        self._check_draft()
        for spec in self:
            if not spec.line_ids:
                raise UserError(self.env._("Compute the specification first."))
        self.write(
            {
                "state": "prepared",
                "prepared_by_id": self.env.user.id,
                "prepared_date": fields.Datetime.now(),
            }
        )
        return True

    def action_check(self):
        if any(spec.state != "prepared" for spec in self):
            raise UserError(self.env._("Only a prepared specification is checked."))
        self.write(
            {
                "state": "checked",
                "checked_by_id": self.env.user.id,
                "checked_date": fields.Datetime.now(),
            }
        )
        return True

    def action_reset_to_draft(self):
        self.write(
            {
                "state": "draft",
                "prepared_by_id": False,
                "prepared_date": False,
                "checked_by_id": False,
                "checked_date": False,
            }
        )
        return True

    def action_print_pdf(self):
        return self.env.ref(
            "account_balance_sheet_specification."
            "account_balance_sheet_specification_report_pdf"
        ).report_action(self)

    def action_print_xlsx(self):
        return self.env.ref(
            "account_balance_sheet_specification."
            "account_balance_sheet_specification_report_xlsx"
        ).report_action(self)

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _move_line_domain(self):
        self.ensure_one()
        return [
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
            ("date", "<=", self.date),
        ]

    def _get_balances(self):
        """``{account: balance}`` of the balance sheet accounts with a
        balance, and the balance of the profit and loss accounts."""
        self.ensure_one()
        groups = self.env["account.move.line"]._read_group(
            self._move_line_domain(),
            groupby=["account_id"],
            aggregates=["balance:sum"],
        )
        balances = {}
        profit_and_loss = 0.0
        currency = self.currency_id
        for account, balance in groups:
            if account.account_type in PROFIT_AND_LOSS_TYPES:
                profit_and_loss += balance
            elif account.account_type != "off_balance" and not currency.is_zero(
                balance
            ):
                balances[account] = balance
        return balances, profit_and_loss

    @api.model
    def _get_group_name(self, account):
        tag = account.tag_ids.filtered(lambda t: t.applicability == "accounts")[:1]
        if tag:
            return tag.name
        types = dict(account._fields["account_type"]._description_selection(self.env))
        return types.get(account.account_type, account.account_type)

    def _compute_lines(self):
        self.ensure_one()
        balances, profit_and_loss = self._get_balances()
        Line = self.env["account.balance.sheet.specification.line"]
        lines_by_account = {line.account_id: line for line in self.line_ids}
        # Drop lines that no longer have a balance or anything typed by hand
        for account, line in lines_by_account.items():
            if account not in balances and not line._has_manual_content():
                line.unlink()
        accounts = sorted(balances, key=lambda a: a.code or "")
        group_order = {}
        for account in accounts:
            group_order.setdefault(self._get_group_name(account), len(group_order))
        new_lines = Line
        for index, account in enumerate(accounts):
            group = self._get_group_name(account)
            values = {
                "balance": balances[account],
                "group_name": group,
                "sequence": group_order[group] * 10000 + index,
            }
            line = lines_by_account.get(account)
            if line and line.exists():
                line.write(values)
            else:
                values.update({"specification_id": self.id, "account_id": account.id})
                new_lines |= Line.create(values)
        for line in self.line_ids.filtered(
            lambda line: line.account_id not in balances
        ):
            line.balance = 0.0
        self._compute_auto_items()
        if self.previous_id:
            new_lines._copy_from_previous(self.previous_id)
        assets = liabilities = equity = 0.0
        for account, balance in balances.items():
            if account.account_type.startswith("asset"):
                assets += balance
            elif account.account_type.startswith("liability"):
                liabilities -= balance
            else:
                equity -= balance
        self.write(
            {
                "total_assets": assets,
                "total_liabilities": liabilities,
                "total_equity": equity,
                "unallocated_earnings": -profit_and_loss,
                "computed_date": fields.Datetime.now(),
            }
        )

    def _compute_auto_items(self):
        self.ensure_one()
        lines = self.line_ids
        lines.item_ids.filtered(lambda item: item.kind == "auto").unlink()
        lines.write({"method": "manual"})
        accounts = lines.account_id
        Item = self.env["account.balance.sheet.specification.item"]
        for account_id, (method, items) in self._get_auto_items(accounts).items():
            line = lines.filtered(lambda line, a=account_id: line.account_id.id == a)
            if not line:
                continue
            line.method = method
            Item.create(
                [dict(values, line_id=line.id, kind="auto") for values in items]
            )

    def _get_auto_items(self, accounts):
        """``{account id: (method, [item values])}`` for the accounts whose
        balance Odoo can itemize. Extend it to itemize more accounts; leave
        the accounts already in the result alone."""
        self.ensure_one()
        result = {}
        result.update(self._get_bank_items(accounts))
        open_item_accounts = accounts.filtered(
            lambda a: a.reconcile
            and a.account_type not in ("asset_cash", "liability_credit_card")
            and a.id not in result
        )
        result.update(self._get_open_items(open_item_accounts))
        return result

    def _get_open_items(self, accounts):
        """Open items on the date, per partner: what was not yet matched by
        the date, so later payments do not count."""
        self.ensure_one()
        if not accounts:
            return {}
        date = self.date
        lines = self.env["account.move.line"].search(
            self._move_line_domain()
            + [
                ("account_id", "in", accounts.ids),
                "|",
                ("reconciled", "=", False),
                "|",
                ("matched_debit_ids.max_date", ">", date),
                ("matched_credit_ids.max_date", ">", date),
            ]
        )
        amounts = defaultdict(float)
        counts = defaultdict(int)
        for line in lines:
            matched = line.matched_credit_ids.filtered(
                lambda p: p.max_date <= date
            ).mapped("amount")
            matched_debit = line.matched_debit_ids.filtered(
                lambda p: p.max_date <= date
            ).mapped("amount")
            residual = line.balance - sum(matched) + sum(matched_debit)
            if self.currency_id.is_zero(residual):
                continue
            key = (line.account_id.id, line.partner_id.commercial_partner_id.id)
            amounts[key] += residual
            counts[key] += 1
        result = {}
        partners = self.env["res.partner"].browse(
            {partner_id for _account, partner_id in amounts if partner_id}
        )
        names = {partner.id: partner.display_name for partner in partners}
        for (account_id, partner_id), amount in sorted(
            amounts.items(), key=lambda kv: names.get(kv[0][1], "")
        ):
            if self.currency_id.is_zero(amount):
                continue
            label = names.get(partner_id) or self.env._("Without partner")
            items = result.setdefault(account_id, ("open_items", []))[1]
            items.append(
                {
                    "name": self.env._(
                        "%(partner)s (%(count)s open items)",
                        partner=label,
                        count=counts[(account_id, partner_id)],
                    ),
                    "partner_id": partner_id or False,
                    "amount": amount,
                }
            )
        return result

    def _get_bank_items(self, accounts):
        """For a bank or cash account: the closing balance of the journal's
        last bank statement on or before the date."""
        self.ensure_one()
        result = {}
        journals = self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("default_account_id", "in", accounts.ids),
            ]
        )
        Statement = self.env["account.bank.statement"]
        for journal in journals:
            statement = Statement.search(
                [("journal_id", "=", journal.id), ("date", "<=", self.date)],
                order="date desc, id desc",
                limit=1,
            )
            if not statement:
                continue
            items = result.setdefault(
                journal.default_account_id.id, ("bank_statement", [])
            )[1]
            items.append(
                {
                    "name": self.env._(
                        "%(journal)s: statement %(statement)s",
                        journal=journal.name,
                        statement=statement.name or statement.date,
                    ),
                    "date": statement.date,
                    "reference": statement.reference or False,
                    "amount": statement.balance_end_real,
                    "res_model": statement._name,
                    "res_id": statement.id,
                }
            )
        return result

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def _get_report_groups(self):
        """``[(group name, lines)]`` in report order."""
        self.ensure_one()
        groups = []
        for line in self.line_ids.sorted("sequence"):
            if not groups or groups[-1][0] != line.group_name:
                groups.append((line.group_name, line))
            else:
                groups[-1] = (groups[-1][0], groups[-1][1] | line)
        return groups
