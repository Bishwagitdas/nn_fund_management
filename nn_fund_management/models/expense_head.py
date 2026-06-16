from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpenseHead(models.Model):
    _name = 'nn.expense.head'
    _description = 'Expense Head'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Expense Head Name', required=True, tracking=True)
    code = fields.Char(string='Code')
    category = fields.Selection([
        ('office_rent', 'Office Rent'),
        ('salary', 'Salary'),
        ('utility', 'Utility Expenses'),
        ('marketing', 'Marketing Expenses'),
        ('administrative', 'Administrative Expenses'),
        ('other', 'Other'),
    ], string='Category', required=True, default='other')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    total_allocated = fields.Monetary(string='Total Allocated', compute='_compute_balances',
                                       store=True, currency_field='currency_id')
    available_fund = fields.Monetary(string='Available Fund', compute='_compute_balances',
                                      store=True, currency_field='currency_id')
    requisition_hold = fields.Monetary(string='Requisition Hold', compute='_compute_balances',
                                        store=True, currency_field='currency_id')
    transfer_hold = fields.Monetary(string='Transfer Hold', compute='_compute_balances',
                                     store=True, currency_field='currency_id')
    approved_unspent = fields.Monetary(string='Approved (Unspent)', compute='_compute_balances',
                                        store=True, currency_field='currency_id')
    total_spent = fields.Monetary(string='Total Spent', compute='_compute_balances',
                                   store=True, currency_field='currency_id')
    incoming_transfers = fields.Monetary(string='Incoming Transfers', compute='_compute_balances',
                                          store=True, currency_field='currency_id')
    outgoing_transfers = fields.Monetary(string='Outgoing Transfers', compute='_compute_balances',
                                          store=True, currency_field='currency_id')

    allocation_ids = fields.One2many('nn.fund.allocation', 'expense_head_id', string='Allocations')
    requisition_ids = fields.One2many('nn.fund.requisition', 'expense_head_id', string='Requisitions')
    bill_ids = fields.One2many('nn.fund.bill', 'expense_head_id', string='Bills')

    @api.depends(
        'allocation_ids.amount', 'allocation_ids.state',
        'requisition_ids.amount', 'requisition_ids.state',
        'bill_ids.amount', 'bill_ids.state',
    )
    def _compute_balances(self):
        Transfer = self.env['nn.fund.transfer']
        for rec in self:
            approved_allocs = rec.allocation_ids.filtered(lambda a: a.state == 'approved')
            total_allocated = sum(approved_allocs.mapped('amount'))

            incoming_t = Transfer.search([('destination_expense_head_id', '=', rec.id),
                                          ('state', '=', 'approved')])
            outgoing_t = Transfer.search([('source_expense_head_id', '=', rec.id),
                                          ('state', '=', 'approved')])
            inc_amount = sum(incoming_t.mapped('amount'))
            out_amount = sum(outgoing_t.mapped('amount'))

            req_hold = sum(rec.requisition_ids.filtered(
                lambda r: r.state in ('submitted', 'gm_approved')).mapped('amount'))
            transfer_hold_out = sum(Transfer.search([
                ('source_expense_head_id', '=', rec.id),
                ('state', 'in', ('submitted', 'gm_approved'))
            ]).mapped('amount'))

            approved_reqs = rec.requisition_ids.filtered(lambda r: r.state == 'approved')
            approved_unspent = sum(approved_reqs.mapped('remaining_billable_amount'))

            posted_bills = rec.bill_ids.filtered(lambda b: b.state == 'posted')
            spent = sum(posted_bills.mapped('amount'))

            rec.total_allocated = total_allocated
            rec.incoming_transfers = inc_amount
            rec.outgoing_transfers = out_amount
            rec.requisition_hold = req_hold
            rec.transfer_hold = transfer_hold_out
            rec.approved_unspent = approved_unspent
            rec.total_spent = spent
            rec.available_fund = (total_allocated + inc_amount - out_amount
                                  - req_hold - transfer_hold_out - approved_unspent - spent)

    @api.constrains('available_fund')
    def _check_no_negative_balance(self):
        for rec in self:
            if rec.available_fund < -0.01:
                raise ValidationError(f'Expense head "{rec.name}" cannot have a negative balance.')

    def unlink(self):
        for rec in self:
            if rec.allocation_ids or rec.requisition_ids:
                raise UserError('Cannot delete an expense head that has allocations or requisitions.')
        return super().unlink()
