# Copyright 2026 Cetmix Nordic Ltd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountBalanceSheetSpecificationXlsx(models.AbstractModel):
    _name = "report.account_balance_sheet_specification.specification_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Balance Sheet Specification Excel Report"

    def generate_xlsx_report(self, workbook, data, specifications):
        bold = workbook.add_format({"bold": True})
        group_format = workbook.add_format({"bold": True, "bg_color": "#DDDDDD"})
        money = workbook.add_format({"num_format": "#,##0.00"})
        money_bold = workbook.add_format({"num_format": "#,##0.00", "bold": True})
        date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
        _ = self.env._
        for spec in specifications:
            sheet = workbook.add_worksheet(f"{spec.date}"[:31])
            sheet.set_column(0, 0, 14)
            sheet.set_column(1, 1, 50)
            sheet.set_column(2, 3, 16)
            sheet.set_column(4, 6, 18)
            sheet.write(0, 0, spec.name, bold)
            sheet.write(1, 0, _("Date"))
            sheet.write_datetime(1, 1, spec.date, date_format)
            sheet.write(2, 0, _("Prepared by"))
            sheet.write(2, 1, spec.prepared_by_id.name or "")
            sheet.write(3, 0, _("Checked by"))
            sheet.write(3, 1, spec.checked_by_id.name or "")
            row = 5
            headers = [
                _("Account"),
                _("Description"),
                _("Balance / amount"),
                _("Unexplained"),
                _("Partner"),
                _("Reference"),
                _("Date"),
            ]
            for col, header in enumerate(headers):
                sheet.write(row, col, header, bold)
            row += 1
            for group_name, lines in spec._get_report_groups():
                sheet.merge_range(row, 0, row, 6, group_name, group_format)
                row += 1
                for line in lines:
                    sheet.write(row, 0, line.account_id.code or "", bold)
                    sheet.write(row, 1, line.account_id.name, bold)
                    sheet.write_number(row, 2, line.balance, money_bold)
                    sheet.write_number(row, 3, line.difference, money)
                    row += 1
                    for item in line.item_ids:
                        sheet.write(row, 1, item.name)
                        sheet.write_number(row, 2, item.amount, money)
                        sheet.write(row, 4, item.partner_id.name or "")
                        sheet.write(row, 5, item.reference or "")
                        if item.date:
                            sheet.write_datetime(row, 6, item.date, date_format)
                        row += 1
                    if line.note:
                        sheet.write(row, 1, line.note)
                        row += 1
            row += 1
            for label, value in (
                (_("Total assets"), spec.total_assets),
                (_("Total liabilities"), spec.total_liabilities),
                (_("Total equity"), spec.total_equity),
                (_("Unallocated earnings"), spec.unallocated_earnings),
            ):
                sheet.write(row, 1, label, bold)
                sheet.write_number(row, 2, value, money_bold)
                row += 1
