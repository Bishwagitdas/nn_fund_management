from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class FundRequisition(models.Model):
    _name = 'nn.fund.requisition'
    _description = 'Fund Requisition'
    _inherit = ['nn.approval.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    state = fields.Selection(selection_add=[
        ('closed', 'Closed'),
    ], ondelete={'closed': 'set draft'})

    name = fields.Char(string='Requisition Number', required=True, copy=False,
                        default=lambda self: self.env['ir.sequence'].next_by_code('nn.fund.requisition'))
    project_id = fields.Many2one('nn.fund.project', string='Project', tracking=True)
    expense_head_id = fields.Many2one('nn.expense.head', string='Expense Head', tracking=True)
    amount = fields.Monetary(string='Requested Amount', required=True,
                              currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    purpose = fields.Text(string='Purpose', required=True)
    request_date = fields.Date(string='Request Date', required=True, default=fields.Date.today)
    required_date = fields.Date(string='Required Date')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    requisition_type = fields.Selection([
        ('project', 'Project'),
        ('expense_head', 'Expense Head'),
    ], string='Requisition For', required=True, default='project')

    remaining_billable_amount = fields.Monetary(string='Remaining Billable',
                                                 compute='_compute_remaining', store=True,
                                                 currency_field='currency_id')
    bill_ids = fields.One2many('nn.fund.bill', 'requisition_id', string='Bills')
    total_billed = fields.Monetary(string='Total Billed', compute='_compute_remaining',
                                    store=True, currency_field='currency_id')

    @api.depends('bill_ids.amount', 'bill_ids.state', 'amount', 'state')
    def _compute_remaining(self):
        for rec in self:
            posted = sum(rec.bill_ids.filtered(lambda b: b.state == 'posted').mapped('amount'))
            rec.total_billed = posted
            if rec.state == 'approved':
                rec.remaining_billable_amount = rec.amount - posted
            else:
                rec.remaining_billable_amount = 0.0

    @api.constrains('project_id', 'expense_head_id', 'requisition_type')
    def _check_project_or_expense(self):
        for rec in self:
            if rec.requisition_type == 'project' and not rec.project_id:
                raise ValidationError('Please select a project.')
            if rec.requisition_type == 'expense_head' and not rec.expense_head_id:
                raise ValidationError('Please select an expense head.')
            if rec.project_id and rec.expense_head_id:
                raise ValidationError('A requisition must use either a project or an expense head.')

    def _validate_before_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError('Requisition amount must be greater than zero.')
            if rec.requisition_type == 'project' and rec.project_id:
                rec.project_id._compute_balances()
                available = rec.project_id.available_fund
                source_name = rec.project_id.name
            elif rec.requisition_type == 'expense_head' and rec.expense_head_id:
                rec.expense_head_id._compute_balances()
                available = rec.expense_head_id.available_fund
                source_name = rec.expense_head_id.name
            else:
                raise UserError('Please select a project or expense head.')
            if available < rec.amount:
                raise UserError(
                    f'Insufficient available balance in "{source_name}". '
                    f'Available: {available:.2f}, Requested: {rec.amount:.2f}'
                )

    def _on_submit(self):
        if self.project_id:
            self.project_id._compute_balances()
        if self.expense_head_id:
            self.expense_head_id._compute_balances()

    def _on_approve(self):
        if self.project_id:
            self.project_id._compute_balances()
        if self.expense_head_id:
            self.expense_head_id._compute_balances()

    def _on_reject(self):
        if self.project_id:
            self.project_id._compute_balances()
        if self.expense_head_id:
            self.expense_head_id._compute_balances()

    def _on_cancel(self):
        self._on_reject()

    def action_close(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError('Only approved requisitions can be closed.')
            if rec.remaining_billable_amount > 0.01:
                # Release unused amount back to project/expense
                rec.message_post(
                    body=f'Requisition closed. Unused amount {rec.remaining_billable_amount:.2f} released back.')
            rec.state = 'closed'
            if rec.project_id:
                rec.project_id._compute_balances()
            if rec.expense_head_id:
                rec.expense_head_id._compute_balances()
