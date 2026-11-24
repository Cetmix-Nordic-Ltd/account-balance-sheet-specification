Balance sheet specification (in Finnish *tase-erittely*) for Odoo
Community: every balance sheet account on a closing date with its
balance and the items that make it up, signed off by the person who
prepared it and the person who checked it.

- Accounts are grouped by their account tag (for example the balance
  sheet items of the Finnish chart of accounts of `l10n_fi_oca`), or by
  account type when they have none.
- Odoo itemizes what it can:
  - receivable, payable and other reconcilable accounts: the items open
    on the date, per partner; payments made after the date do not count;
  - bank and cash accounts: the closing balance of the last bank
    statement on or before the date.
- Other accounts are explained by hand: items (for example loans or
  accruals), a note and attached documents. Each account shows what is
  still unexplained.
- Items typed by hand are copied from the previous specification as a
  starting point.
- States *Draft*, *Prepared* and *Checked*; a prepared or checked
  specification cannot be changed.
- PDF and Excel reports.

More itemizations come with:

| Module | Itemizes |
|---|---|
| `account_balance_sheet_specification_asset` | Fixed asset accounts per asset (`account_asset_management`) |
| `account_balance_sheet_specification_stock` | Inventory accounts per product category |
