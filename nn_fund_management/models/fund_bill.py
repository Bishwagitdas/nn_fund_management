from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class FundBill(models.Model):
    _name = 'nn.fund.bill'
    _description = 'Fund Bill'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'bill_date desc, id desc'

    name = fields.Char(string='Bill Number', required=True, copy=False,
                        default=lambda self: self.env['ir.sequence'].next_by_code('nn.fund.bill'))
    requisition_id = fields.Many2one('nn.fund.requisition', string='Requisition',
                                      required=True, tracking=True,
                                      domain="[('state', '=', 'approved')]")
    project_id = fields.Many2one('nn.fund.project', string='Project',
                                  related='requisition_id.project_id', store=True)
    expense_head_id = fields.Many2one('nn.expense.head', string='Expense Head',
                                       related='requisition_id.expense_head_id', store=True)
    amount = fields.Monetary(string='Bill Amount', required=True,
                              currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    bill_date = fields.Date(string='Bill Date', required=True, default=fields.Date.today)
    vendor = fields.Char(string='Vendor / Payee')
    description = fields.Text(string='Description')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    @api.constrains('amount', 'requisition_id')
    def _check_bill_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError('Bill amount must be greater than zero.')
            if rec.requisition_id and rec.state != 'cancelled':
                req = rec.requisition_id
                if req.state != 'approved':
                    raise ValidationError('Bill can only be created against an approved requisition.')
                other_bills = req.bill_ids.filtered(
                    lambda b: b.id != rec.id and b.state == 'posted')
                already_billed = sum(other_bills.mapped('amount'))
                if already_billed + rec.amount > req.amount + 0.01:
                    raise ValidationError(
                        f'Total billed amount ({already_billed + rec.amount:.2f}) '
                        f'would exceed the approved requisition amount ({req.amount:.2f}). '
                        f'Remaining billable: {req.amount - already_billed:.2f}'
                    )

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft bills can be posted.')
            req = rec.requisition_id
            if req.state != 'approved':
                raise UserError('The linked requisition must be approved before posting a bill.')
            # Validate amount against remaining billable at post time (concurrency safe)
            other_posted = sum(req.bill_ids.filtered(
                lambda b: b.id != rec.id and b.state == 'posted').mapped('amount'))
            if other_posted + rec.amount > req.amount + 0.01:
                raise UserError(
                    f'Cannot post: bill amount exceeds remaining billable. '
                    f'Remaining: {req.amount - other_posted:.2f}'
                )
            rec.state = 'posted'
            rec.message_post(body=f'Bill posted by {self.env.user.name}. Amount: {rec.amount:.2f}')
            req.sudo()._compute_remaining()
            if rec.project_id:
                rec.project_id.sudo()._compute_balances()
            if rec.expense_head_id:
                rec.expense_head_id.sudo()._compute_balances()

    def action_cancel(self):
        for rec in self:
            if rec.state == 'cancelled':
                raise UserError('Bill is already cancelled.')
            was_posted = rec.state == 'posted'
            rec.state = 'cancelled'
            rec.message_post(body=f'Bill cancelled by {self.env.user.name}.')
            if was_posted:
                # Restore amount back to requisition remaining billable
                rec.requisition_id.sudo()._compute_remaining()
                if rec.project_id:
                    rec.project_id.sudo()._compute_balances()
                if rec.expense_head_id:
                    rec.expense_head_id.sudo()._compute_balances()

    def unlink(self):
        for rec in self:
            if rec.state == 'posted':
                raise UserError('Cannot delete a posted bill. Please cancel it first.')
        return super().unlink()
