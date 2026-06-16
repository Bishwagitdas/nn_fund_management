from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError


class TestSecurity(TransactionCase):

    def setUp(self):
        super().setUp()
        group_user = self.env.ref('nn_fund_management.group_fund_user')
        group_finance = self.env.ref('nn_fund_management.group_fund_finance_user')
        group_gm = self.env.ref('nn_fund_management.group_fund_gm_approver')
        group_admin = self.env.ref('nn_fund_management.group_fund_administrator')

        self.user_plain = self.env['res.users'].create({
            'name': 'Plain Fund User', 'login': 'plain@test.com',
            'groups_id': [(4, group_user.id)],
        })
        self.user_finance = self.env['res.users'].create({
            'name': 'Finance', 'login': 'finance2@test.com',
            'groups_id': [(4, group_finance.id)],
        })
        self.user_gm = self.env['res.users'].create({
            'name': 'GM', 'login': 'gm2@test.com',
            'groups_id': [(4, group_gm.id)],
        })
        self.user_admin = self.env['res.users'].create({
            'name': 'Admin', 'login': 'admin2@test.com',
            'groups_id': [(4, group_admin.id)],
        })
        self.account = self.env['nn.fund.account'].create({
            'name': 'Security Test Account', 'account_type': 'bank',
            'company_id': self.env.company.id,
        })

    def test_plain_user_cannot_confirm_incoming_fund(self):
        """Fund User without finance role cannot confirm incoming funds."""
        fund = self.env['nn.incoming.fund'].create({
            'fund_account_id': self.account.id,
            'date': '2025-01-01', 'amount': 100000,
            'transaction_ref': 'SEC-001', 'sender': 'Test',
        })
        with self.assertRaises(UserError):
            fund.with_user(self.user_plain).action_confirm()

    def test_finance_user_can_confirm(self):
        """Finance user can confirm incoming funds."""
        fund = self.env['nn.incoming.fund'].create({
            'fund_account_id': self.account.id,
            'date': '2025-01-01', 'amount': 100000,
            'transaction_ref': 'SEC-002', 'sender': 'Test',
        })
        fund.with_user(self.user_finance).action_confirm()
        self.assertEqual(fund.state, 'confirmed')

    def test_confirmed_fund_cannot_be_deleted(self):
        """Confirmed fund cannot be deleted."""
        fund = self.env['nn.incoming.fund'].with_user(self.user_finance).create({
            'fund_account_id': self.account.id,
            'date': '2025-01-01', 'amount': 100000,
            'transaction_ref': 'SEC-003', 'sender': 'Test',
        })
        fund.with_user(self.user_finance).action_confirm()
        with self.assertRaises(UserError):
            fund.with_user(self.user_admin).unlink()

    def test_self_approval_blocked(self):
        """User cannot approve their own allocation."""
        config = self.env['nn.fund.config'].create({
            'name': 'Sec Config', 'company_id': self.env.company.id,
            'gm_approver_ids': [(4, self.user_gm.id)],
            'md_approver_ids': [(4, self.user_gm.id)],
        })
        fund = self.env['nn.incoming.fund'].with_user(self.user_finance).create({
            'fund_account_id': self.account.id,
            'date': '2025-01-01', 'amount': 500000,
            'transaction_ref': 'SEC-SELF', 'sender': 'Test',
        })
        fund.with_user(self.user_finance).action_confirm()
        project = self.env['nn.fund.project'].create({
            'name': 'Sec Project', 'company_id': self.env.company.id})
        alloc = self.env['nn.fund.allocation'].with_user(self.user_gm).create({
            'fund_account_id': self.account.id,
            'allocation_type': 'project', 'project_id': project.id,
            'amount': 100000, 'purpose': 'Self approval test',
        })
        alloc.with_user(self.user_gm).action_submit()
        with self.assertRaises(UserError):
            alloc.with_user(self.user_gm).action_approve_gm()
