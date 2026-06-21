from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class FundAllocation(models.Model):
    _name = 'nn.fund.allocation'
    _description = 'Fund Allocation'
    _inherit = ['nn.approval.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(string='Request Number', required=True, copy=False,
                        default=lambda self: self.env['ir.sequence'].next_by_code('nn.fund.allocation'))
    fund_account_id = fields.Many2one('nn.fund.account', string='Fund Account',
                                       required=True, tracking=True)
    project_id = fields.Many2one('nn.fund.project', string='Project', tracking=True)
    expense_head_id = fields.Many2one('nn.expense.head', string='Expense Head', tracking=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', related='fund_account_id.currency_id', store=True)
    purpose = fields.Text(string='Purpose', required=True)
    request_date = fields.Date(string='Request Date', required=True, default=fields.Date.today)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    allocation_type = fields.Selection([
        ('project', 'Project'),
        ('expense_head', 'Expense Head'),
    ], string='Allocate To', required=True, default='project')

    @api.constrains('project_id', 'expense_head_id', 'allocation_type')
    def _check_project_or_expense(self):
        for rec in self:
            if rec.allocation_type == 'project' and not rec.project_id:
                raise ValidationError('Please select a project for project-type allocation.')
            if rec.allocation_type == 'expense_head' and not rec.expense_head_id:
                raise ValidationError('Please select an expense head for expense-type allocation.')
            if rec.project_id and rec.expense_head_id:
                raise ValidationError('An allocation must use either a project or an expense head, not both.')

    def _validate_before_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError('Allocation amount must be greater than zero.')
            account = rec.fund_account_id
            account.sudo()._compute_balances()
            if account.unassigned_balance < rec.amount:
                raise UserError(
                    f'Insufficient unassigned balance. '
                    f'Available: {account.unassigned_balance:.2f}, '
                    f'Requested: {rec.amount:.2f}'
                )

    def _on_submit(self):
        # Amount moves from unassigned → on hold (computed automatically via _compute_balances)
        self.fund_account_id.sudo()._compute_balances()

    def _on_approve(self):
        # Amount moves from on hold → assigned to project/expense
        self.fund_account_id.sudo()._compute_balances()
        if self.project_id:
            self.project_id.sudo()._compute_balances()
        if self.expense_head_id:
            self.expense_head_id.sudo()._compute_balances()

    def _on_reject(self):
        # Amount returns from hold → unassigned
        self.fund_account_id.sudo()._compute_balances()

    def _on_cancel(self):
        self.fund_account_id.sudo()._compute_balances()
        if self.project_id:
            self.project_id.sudo()._compute_balances()
        if self.expense_head_id:
            self.expense_head_id.sudo()._compute_balances()
