# NN Fund Management — Odoo Module

Odoo module to manage incoming funds, allocations, requisitions, bills, and transfers with a GM → MD approval flow.

---

## Basic Info

- **Odoo Version:** 17.0 (Community or Enterprise)
- **Module Name:** `nn_fund_management`
- **Depends on:** `base`, `mail`, `account`

---

## Folder Structure

```
nn_fund_management/
├── models/             # all business logic
├── views/               # screens / menus
├── security/           # access rights & groups
├── data/                  # sequences
├── wizard/             # bank email test tool
└── tests/                 # automated tests
```

---

## How to Install (Docker)

```bash
git clone <your-repo-url>
cd <repo-folder>
docker compose up -d
```
1. Open `http://localhost:8069`
2. Create a database (master password: `admin_master_password`)
3. Install the module:
```bash
docker compose exec odoo odoo -i nn_fund_management -d odoo --stop-after-init
```

---

## How to Install (Without Docker)

```bash
cp -r nn_fund_management /path/to/odoo/custom-addons/
```

1. Add the addons path in `odoo.conf`
2. Restart Odoo: `./odoo-bin -c odoo.conf`
3. Go to **Settings → Technical → Update Apps List**
4. Install from **Apps → Fund Management**

Or via CLI:
```bash
./odoo-bin -i nn_fund_management -d your_database --config=odoo.conf
```

---

## Setup After Install

1. **Give users a group** (Settings → Users):
   - `Fund User` – create requests
   - `Finance User` – confirm funds, post bills
   - `GM Approver` / `MD Approver` – approve
   - `Fund Administrator` – full access

2. **Set approvers**: Fund Management → Configuration → Fund Settings → add GM and MD approvers (required, or approval won't work)

3. **Create Fund Accounts**, **Projects**, and **Expense Heads** under their menus

---

## How to Test

```bash
docker compose exec odoo odoo --test-enable --stop-after-init -i nn_fund_management -d odoo
```

Or manually in the UI:
1. Confirm an incoming fund
2. Allocate part of it to a project → approve with GM then MD
3. Transfer between two projects → approve
4. Create a requisition → approve → post a bill against it
5. Try to post a bill bigger than what's left → should be blocked

---

## What This Module Assumes

- One company = one set of GM/MD approvers
- Approval is always GM first, then MD
- Bills are a custom model, not linked to Odoo's accounting entries
- "Closed" requisition = no more bills can be added to it

---

## Limitations

- **Bank email parsing** only works on text you paste in manually — there's no live email inbox connected, so it can't automatically read real bank emails yet
- **Approval rules by amount** exist as a setting, but the actual approve buttons still always follow GM → MD — they don't switch approvers based on the rule yet
- Dashboard is just numbers and lists, not charts or graphs
- No support for converting between different currencies
- Bills don't create real accounting/journal entries
- No printable PDF vouchers or reports
- No mobile-specific view, only the standard Odoo responsive layout

---

## Why Some Things Were Built This Way

- **One mixin for approvals** – Allocation, Requisition, and Transfer all share the same approval steps (`nn.approval.mixin`), so the GM→MD logic is written once
- **Balances are always calculated, never typed in** – this stops numbers from going out of sync
- **Negative balances and double-spending are blocked on the server**, not just hidden in the UI, so it can't be bypassed
- **Deleting confirmed/approved records is blocked** to keep a clean audit trail