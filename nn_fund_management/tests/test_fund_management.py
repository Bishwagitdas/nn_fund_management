from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestFundManagement(TransactionCase):

    def setUp(self):
        super().setUp()
        # Create test users
        group_finance = self.env.ref('nn_fund_management.group_fund_finance_user')
        group_gm = self.env.ref('nn_fund_management.group_fund_gm_approver')
        group_md = self.env.ref('nn_fund_management.group_fund_md_approver')
        group_admin = self.env.ref('nn_fund_management.group_fund_administrator')

        self.user_finance = self.env['res.users'].create({
            'name': 'Finance User', 'login': 'finance_test@test.com',
            'groups_id': [(4, group_finance.id)],
        })
        self.user_gm = self.env['res.users'].create({
            'name': 'GM User', 'login': 'gm_test@test.com',
            'groups_id': [(4, group_gm.id)],
        })
        self.user_md = self.env['res.users'].create({
            'name': 'MD User', 'login': 'md_test@test.com',
            'groups_id': [(4, group_md.id)],
        })
        self.user_admin = self.env['res.users'].create({
            'name': 'Admin User', 'login': 'admin_test@test.com',
            'groups_id': [(4, group_admin.id)],
        })
        self.user_requester = self.env['res.users'].create({
            'name': 'Fund User', 'login': 'fund_user_test@test.com',
            'groups_id': [(4, self.env.ref('nn_fund_management.group_fund_user').id)],
        })

        # Config
        self.config = self.env['nn.fund.config'].create({
            'name': 'Test Config',
            'company_id': self.env.company.id,
            'gm_approver_ids': [(4, self.user_gm.id)],
            'md_approver_ids': [(4, self.user_md.id)],
        })

        # Fund Account
        self.account = self.env['nn.fund.account'].create({
            'name': 'Main Fund Account',
            'account_type': 'bank',
            'company_id': self.env.company.id,
        })

        # Projects
        self.project_a = self.env['nn.fund.project'].create({
            'name': 'Project A', 'company_id': self.env.company.id})
        self.project_b = self.env['nn.fund.project'].create({
            'name': 'Project B', 'company_id': self.env.company.id})

    def _confirm_incoming(self, amount, ref='TXN001'):
        fund = self.env['nn.incoming.fund'].with_user(self.user_finance).create({
            'fund_account_id': self.account.id,
            'date': '2025-01-01',
            'amount': amount,
            'transaction_ref': ref,
            'sender': 'Test Sender',
        })
        fund.with_user(self.user_finance).action_confirm()
        return fund

    def _approve_allocation(self, alloc):
        alloc.with_user(self.user_gm).action_approve_gm()
        alloc.with_user(self.user_md).action_approve_md()

    def test_01_incoming_fund_confirm(self):
        """Incoming fund confirm increases unassigned balance."""
        self._confirm_incoming(1000000, 'TXN001')
        self.account._compute_balances()
        self.assertAlmostEqual(self.account.total_received, 1000000)
        self.assertAlmostEqual(self.account.unassigned_balance, 1000000)

    def test_02_duplicate_transaction_ref_blocked(self):
        """Duplicate transaction ref on same account is blocked."""
        self._confirm_incoming(500000, 'TXN-DUP')
        with self.assertRaises(Exception):
            self._confirm_incoming(100000, 'TXN-DUP')

    def test_03_allocation_puts_amount_on_hold(self):
        """Submitting allocation moves amount to hold."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 600000,
            'purpose': 'Test allocation',
        })
        alloc.with_user(self.user_requester).action_submit()
        self.account._compute_balances()
        self.assertAlmostEqual(self.account.on_hold_amount, 600000)
        self.assertAlmostEqual(self.account.unassigned_balance, 400000)

    def test_04_allocation_reject_returns_to_unassigned(self):
        """Rejecting allocation returns amount to unassigned."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 600000,
            'purpose': 'Test',
        })
        alloc.with_user(self.user_requester).action_submit()
        alloc.with_user(self.user_gm).action_reject()
        self.account._compute_balances()
        self.assertAlmostEqual(self.account.unassigned_balance, 1000000)

    def test_05_full_approval_workflow(self):
        """Full allocation approval workflow."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 600000,
            'purpose': 'Test',
        })
        alloc.with_user(self.user_requester).action_submit()
        self.assertEqual(alloc.state, 'submitted')
        alloc.with_user(self.user_gm).action_approve_gm()
        self.assertEqual(alloc.state, 'gm_approved')
        alloc.with_user(self.user_md).action_approve_md()
        self.assertEqual(alloc.state, 'approved')
        self.project_a._compute_balances()
        self.assertAlmostEqual(self.project_a.available_fund, 600000)

    def test_06_insufficient_balance_blocked(self):
        """Cannot allocate more than unassigned balance."""
        self._confirm_incoming(100000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 200000,
            'purpose': 'Test',
        })
        with self.assertRaises(UserError):
            alloc.with_user(self.user_requester).action_submit()

    def test_07_md_cannot_approve_before_gm(self):
        """MD cannot approve before GM."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 100000,
            'purpose': 'Test',
        })
        alloc.with_user(self.user_requester).action_submit()
        with self.assertRaises(UserError):
            alloc.with_user(self.user_md).action_approve_md()

    def test_08_bill_cannot_exceed_requisition(self):
        """Bill cannot exceed requisition's remaining billable amount."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_b.id,
            'amount': 500000,
            'purpose': 'Test',
        })
        alloc.with_user(self.user_requester).action_submit()
        self._approve_allocation(alloc)

        req = self.env['nn.fund.requisition'].with_user(self.user_requester).create({
            'requisition_type': 'project',
            'project_id': self.project_b.id,
            'amount': 150000,
            'purpose': 'Test req',
        })
        req.with_user(self.user_requester).action_submit()
        req.with_user(self.user_gm).action_approve_gm()
        req.with_user(self.user_md).action_approve_md()

        # Post a valid partial bill
        bill = self.env['nn.fund.bill'].with_user(self.user_finance).create({
            'requisition_id': req.id,
            'amount': 100000,
            'bill_date': '2025-01-15',
            'vendor': 'Vendor A',
        })
        bill.with_user(self.user_finance).action_post()
        req._compute_remaining()
        self.assertAlmostEqual(req.remaining_billable_amount, 50000)

        # Try to post a bill exceeding remaining - should fail
        bill2 = self.env['nn.fund.bill'].with_user(self.user_finance).create({
            'requisition_id': req.id,
            'amount': 60000,
            'bill_date': '2025-01-15',
            'vendor': 'Vendor B',
        })
        with self.assertRaises((UserError, ValidationError)):
            bill2.with_user(self.user_finance).action_post()

    def test_09_bill_cancel_restores_requisition(self):
        """Cancelling a posted bill restores remaining billable amount."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 500000,
            'purpose': 'Test',
        })
        alloc.with_user(self.user_requester).action_submit()
        self._approve_allocation(alloc)

        req = self.env['nn.fund.requisition'].with_user(self.user_requester).create({
            'requisition_type': 'project',
            'project_id': self.project_a.id,
            'amount': 100000,
            'purpose': 'Test req',
        })
        req.with_user(self.user_requester).action_submit()
        req.with_user(self.user_gm).action_approve_gm()
        req.with_user(self.user_md).action_approve_md()

        bill = self.env['nn.fund.bill'].with_user(self.user_finance).create({
            'requisition_id': req.id,
            'amount': 80000,
            'bill_date': '2025-01-15',
            'vendor': 'V',
        })
        bill.with_user(self.user_finance).action_post()
        self.assertAlmostEqual(req.remaining_billable_amount, 20000)
        bill.action_cancel()
        req._compute_remaining()
        self.assertAlmostEqual(req.remaining_billable_amount, 100000)

    def test_10_transfer_workflow(self):
        """Transfer moves funds between projects."""
        self._confirm_incoming(1000000)
        alloc = self.env['nn.fund.allocation'].with_user(self.user_requester).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project',
            'project_id': self.project_a.id,
            'amount': 600000,
            'purpose': 'Test',
        })
        alloc.with_user(self.user_requester).action_submit()
        self._approve_allocation(alloc)
        self.project_a._compute_balances()
        self.assertAlmostEqual(self.project_a.available_fund, 600000)

        transfer = self.env['nn.fund.transfer'].with_user(self.user_requester).create({
            'transfer_type': 'project_project',
            'source_project_id': self.project_a.id,
            'destination_project_id': self.project_b.id,
            'amount': 200000,
            'reason': 'Test transfer',
        })
        transfer.with_user(self.user_requester).action_submit()
        self.project_a._compute_balances()
        self.assertAlmostEqual(self.project_a.transfer_hold, 200000)

        transfer.with_user(self.user_gm).action_approve_gm()
        transfer.with_user(self.user_md).action_approve_md()
        self.project_a._compute_balances()
        self.project_b._compute_balances()
        self.assertAlmostEqual(self.project_a.available_fund, 400000)
        self.assertAlmostEqual(self.project_b.available_fund, 200000)

    def test_11_same_source_destination_transfer_blocked(self):
        """Transfer to same source/destination is blocked."""
        with self.assertRaises((UserError, ValidationError)):
            t = self.env['nn.fund.transfer'].create({
                'transfer_type': 'project_project',
                'source_project_id': self.project_a.id,
                'destination_project_id': self.project_a.id,
                'amount': 10000,
                'reason': 'Should fail',
            })
            t.action_submit()

    def test_12_confirmed_incoming_fund_cannot_be_deleted(self):
        """Confirmed incoming funds cannot be deleted."""
        fund = self._confirm_incoming(500000, 'TXN-DEL')
        with self.assertRaises(UserError):
            fund.unlink()
