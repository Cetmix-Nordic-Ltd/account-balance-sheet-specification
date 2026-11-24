# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSpecification(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.receivable = cls.company_data["default_account_receivable"]
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.Spec = cls.env["account.balance.sheet.specification"]
        # Open on 31.12.2025, paid only in January
        cls.open_invoice = cls.init_invoice(
            "out_invoice", invoice_date=date(2025, 12, 10), amounts=[1000.0], post=True
        )
        cls._pay(cls.open_invoice, date(2026, 1, 5))
        # Paid before the date
        cls.paid_invoice = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_b,
            invoice_date=date(2025, 12, 1),
            amounts=[400.0],
            post=True,
        )
        cls._pay(cls.paid_invoice, date(2025, 12, 20))
        # Bank: one statement line and a statement with its closing balance
        st_line = cls.env["account.bank.statement.line"].create(
            {
                "journal_id": cls.bank_journal.id,
                "date": date(2025, 12, 2),
                "amount": 2500.0,
                "payment_ref": "Capital",
            }
        )
        cls.statement = cls.env["account.bank.statement"].create(
            {
                "name": "12/2025",
                "date": date(2025, 12, 31),
                "journal_id": cls.bank_journal.id,
                "line_ids": [Command.set(st_line.ids)],
                "balance_start": 0.0,
                "balance_end_real": 2500.0,
            }
        )

    @classmethod
    def _pay(cls, invoice, day):
        return (
            cls.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"payment_date": day})
            ._create_payments()
        )

    def _spec(self, day=date(2025, 12, 31)):
        spec = self.Spec.create(
            {"name": f"Spec {day}", "date": day, "company_id": self.company.id}
        )
        spec.action_compute()
        return spec

    def _line(self, spec, account):
        return spec.line_ids.filtered(lambda line: line.account_id == account)

    def test_open_items_on_the_date(self):
        spec = self._spec()
        line = self._line(spec, self.receivable)
        self.assertEqual(line.method, "open_items")
        self.assertEqual(line.balance, self.open_invoice.amount_total)
        self.assertEqual(line.item_ids.partner_id, self.partner_a)
        self.assertEqual(line.item_ids.amount, self.open_invoice.amount_total)
        self.assertEqual(line.difference, 0.0)
        # In January the invoice is paid
        january = self._spec(date(2026, 1, 31))
        self.assertFalse(self._line(january, self.receivable))

    def test_bank_statement(self):
        spec = self._spec()
        line = self._line(spec, self.bank_journal.default_account_id)
        self.assertEqual(line.method, "bank_statement")
        self.assertEqual(line.balance, 2500.0)
        self.assertEqual(line.item_ids.amount, 2500.0)
        self.assertEqual(line.item_ids.res_id, self.statement.id)
        self.assertEqual(line.difference, 0.0)

    def test_manual_items_totals_and_recompute(self):
        spec = self._spec()
        self.assertEqual(spec.balance_difference, 0.0)
        self.assertTrue(spec.total_assets)
        manual = spec.line_ids.filtered(lambda line: line.method == "manual")
        self.assertTrue(manual)
        line = manual[0]
        self.assertEqual(line.difference, line.balance)
        before = spec.unexplained_count
        line.write(
            {
                "item_ids": [
                    Command.create({"name": "Explained", "amount": line.balance})
                ],
                "note": "See attachment",
            }
        )
        self.assertEqual(line.difference, 0.0)
        self.assertEqual(spec.unexplained_count, before - 1)
        # Computing again keeps what was typed by hand
        spec.action_compute()
        self.assertTrue(line.exists())
        self.assertEqual(line.manual_amount, line.balance)
        self.assertEqual(line.note, "See attachment")

    def test_workflow_locks(self):
        spec = self._spec()
        line = spec.line_ids[0]
        spec.action_prepare()
        self.assertEqual(spec.prepared_by_id, self.env.user)
        with self.assertRaises(UserError):
            line.write({"item_ids": [Command.create({"name": "x", "amount": 1.0})]})
        with self.assertRaises(UserError):
            line.note = "Too late"
        with self.assertRaises(UserError):
            spec.action_compute()
        spec.action_check()
        self.assertEqual(spec.state, "checked")
        self.assertTrue(spec.checked_date)
        spec.action_reset_to_draft()
        self.assertFalse(spec.prepared_by_id)
        line.note = "Fine again"

    def test_prepare_needs_lines(self):
        spec = self.Spec.create({"name": "Empty", "date": date(2025, 12, 31)})
        with self.assertRaises(UserError):
            spec.action_prepare()
        with self.assertRaises(UserError):
            spec.action_check()

    def test_copy_from_previous(self):
        first = self._spec()
        line = first.line_ids.filtered(lambda line: line.method == "manual")[0]
        line.write(
            {
                "item_ids": [Command.create({"name": "Loan A", "amount": 123.0})],
                "note": "Loan agreement",
            }
        )
        second = self._spec(date(2026, 1, 31))
        self.assertEqual(second.previous_id, first)
        new_line = self._line(second, line.account_id)
        copied = new_line.item_ids.filtered("copied")
        self.assertEqual(copied.name, "Loan A")
        self.assertEqual(copied.amount, 123.0)
        self.assertEqual(new_line.note, "Loan agreement")
        copied.amount = 124.0
        self.assertFalse(copied.copied)

    def test_group_by_tag(self):
        tag = self.env["account.account.tag"].create(
            {"name": "Balance sheet: Accounts receivable", "applicability": "accounts"}
        )
        self.receivable.tag_ids = [Command.link(tag.id)]
        spec = self._spec()
        self.assertEqual(self._line(spec, self.receivable).group_name, tag.name)
        groups = spec._get_report_groups()
        self.assertEqual(sum(len(lines) for _name, lines in groups), len(spec.line_ids))

    def test_reports(self):
        spec = self._spec()
        Report = self.env["ir.actions.report"]
        html = Report._render_qweb_html(
            "account_balance_sheet_specification.specification_document", spec.ids
        )[0]
        self.assertIn(spec.name.encode(), html)
        content, report_type = Report._render(
            "account_balance_sheet_specification.specification_xlsx", spec.ids
        )
        self.assertEqual(report_type, "xlsx")
        self.assertTrue(content.startswith(b"PK"))
        self.company.external_report_layout_id = self.env.ref(
            "web.external_layout_standard"
        )
        self.assertEqual(spec.action_print_xlsx()["type"], "ir.actions.report")
        self.assertEqual(spec.action_print_pdf()["type"], "ir.actions.report")
