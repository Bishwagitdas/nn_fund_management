# NN Fund Management — Odoo Module

Custom Odoo module for managing incoming funds, allocations, requisitions, bills, and transfers with a multi-level approval workflow.

---

## Odoo Version

**Odoo 17.0** (Community or Enterprise)

---

## Module Name

`nn_fund_management`

---

## Dependencies

- `base`
- `mail`
- `account`

---

## Project Structure

```
nn_fund_management/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── fund_config.py          # Approver configuration per company
│   ├── fund_account.py         # Fund bank/cash accounts
│   ├── incoming_fund.py        # Incoming fund records
│   ├── fund_project.py         # Projects with balance tracking
│   ├── expense_head.py         # Expense heads with balance tracking
│   ├── approval_history.py     # Approval log entries
│   ├── approval_mixin.py       # Reusable GM→MD approval workflow
│   ├── fund_allocation.py      # Allocate funds to project/expense head
│   ├── fund_requisition.py     # Request funds from project/expense head
│   ├── fund_bill.py            # Bills against approved requisitions
│   ├── fund_transfer.py        # Transfer between projects/expense heads
│   └── audit_log.py            # Financial audit trail
├── views/
│   ├── fund_account_views.xml
│   ├── incoming_fund_views.xml
│   ├── fund_project_views.xml
│   ├── expense_head_views.xml
│   ├── fund_allocation_views.xml
│   ├── fund_requisition_views.xml
│   ├── fund_bill_views.xml
│   ├── fund_transfer_views.xml
│   ├── dashboard_views.xml
│   └── menu.xml
├── security/
│   ├── groups.xml
│   ├── ir.model.access.csv
│   └── record_rules.xml
├── data/
│   └── sequences.xml
└── tests/
    ├── __init__.py
    ├── test_fund_management.py
    └── test_security.py
```

---

## Installation (Docker — Recommended)

### Prerequisites
- Docker Desktop installed
- Git installed

### Steps

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd <repo-folder>

# 2. Start the containers
docker compose up -d

# 3. Wait ~30 seconds for Odoo to fully start, then open browser
open http://localhost:8069

# 4. Create a new database
#    - Master password: admin_master_password
#    - Database name: odoo
#    - Demo data: optional (uncheck for clean install)

# 5. Install the module
#    Option A: Via UI
#      Go to Apps → search "NN Fund Management" → Install
#
#    Option B: Via CLI (faster)
docker compose exec odoo odoo -i nn_fund_management -d odoo --stop-after-init
```

---

## Installation (Manual without Docker)

### Prerequisites
- Odoo 17.0 installed locally
- PostgreSQL running

### Steps

```bash
# 1. Copy module to Odoo addons path
cp -r nn_fund_management /path/to/odoo/custom-addons/

# 2. Update odoo.conf to include custom addons path
# addons_path = /path/to/odoo/addons,/path/to/odoo/custom-addons

# 3. Restart Odoo
./odoo-bin -c odoo.conf

# 4. Update apps list
# Settings → Technical → Update Apps List

# 5. Install
# Apps → search "Fund Management" → Install

# Or via CLI:
./odoo-bin -i nn_fund_management -d your_database --config=odoo.conf
```

---

## Configuration Steps (After Installation)

1. **Assign security groups to users**
   - Settings → Users → select a user → set their Fund Management group:
     - `Fund User` — basic access, create requests
     - `Finance User` — confirm incoming funds, post bills
     - `GM Approver` — approve at GM level
     - `MD Approver` — approve at MD level
     - `Fund Administrator` — full access including cancel approved records

2. **Configure approvers**
   - Fund Management → Configuration → Fund Settings
   - Create a configuration for your company
   - Add GM Approver users and MD Approver users
   - ⚠️ At least one GM and one MD approver must be set or approval will fail

3. **Create Fund Accounts**
   - Fund Management → Fund Operations → Fund Accounts → New
   - Set name, type (Bank/Cash/Other), currency

4. **Create Projects and Expense Heads**
   - Fund Management → Master Data → Projects → New
   - Fund Management → Master Data → Expense Heads → New

---

## Testing Instructions

### Run all automated tests

```bash
# Via Docker
docker compose exec odoo odoo \
  --test-enable \
  --stop-after-init \
  -i nn_fund_management \
  -d odoo

# Via CLI (non-Docker)
./odoo-bin \
  --test-enable \
  --stop-after-init \
  -i nn_fund_management \
  -d your_database
```

### Manual Demo Scenario

Follow these steps in the UI to verify all features:

1. Confirm BDT 1,000,000 incoming fund
2. Allocate BDT 600,000 to Project A → verify on_hold = 600,000
3. Reject → verify unassigned returns to 1,000,000
4. Re-allocate and fully approve (GM + MD)
5. Transfer BDT 200,000 Project A → Project B → verify transfer hold
6. Approve transfer → verify Project B balance = 200,000
7. Create BDT 150,000 requisition for Project B → approve
8. Post BDT 100,000 partial bill → verify remaining = 50,000
9. Try BDT 60,000 bill → system must block with error
10. Try Project B requisition for Project A → system must block

---

## Assumptions

- Odoo 17.0 Community Edition is used
- A single fund configuration per company is enough (one GM set, one MD set)
- Currency is set at the fund account level; projects/expense heads inherit company currency
- Bills are implemented as a custom model (`nn.fund.bill`) rather than extending `account.move` to keep the module self-contained and not depend on accounting journal setup
- The "closed" state for requisitions means no more bills can be posted against it; unused amount is released back
- Approval sequence is always GM first, then MD — no skipping

---

## Known Limitations

- Email bank parsing (bonus feature) is not implemented in this version
- Dashboard is a basic list/form view; no graphical KPI widgets
- No multi-currency conversion between fund accounts
- Configurable approval rules by amount tier (bonus) are not implemented
- Bills do not integrate with Odoo's native accounting journals/entries
- No PDF report templates (printable vouchers) included

---

## Architecture Notes

### Approval Mixin (`nn.approval.mixin`)
All three workflow models (Allocation, Requisition, Transfer) inherit from an abstract model `nn.approval.mixin`. This mixin provides the full `Draft → Submitted → GM Approved → Approved / Rejected / Cancelled` state machine with hooks (`_on_submit`, `_on_approve`, `_on_reject`, `_on_cancel`) that each child model overrides to handle balance movements. This prevents code duplication and makes adding a new approval level a single-file change.

### Balance Calculation
All balance fields are `compute=..., store=True` fields triggered by changes to related records. They are never manually set. Negative balances are blocked by `@api.constrains`. Double-spend is prevented by checking available balance at submit time with a server-side check (not relying on UI).

### Security
- Five security groups with implied inheritance
- Company-scoped record rules on every model
- Server-side group checks in action methods (hiding buttons alone is not enough)
- `unlink()` overridden on all financial models to block deletion of confirmed/approved records

---
