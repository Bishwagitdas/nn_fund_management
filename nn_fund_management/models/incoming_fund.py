from odoo import models, fields, api
from odoo.exceptions import UserError


class IncomingFund(models.Model):
    _name = 'nn.incoming.fund'
    _description = 'Incoming Fund'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False,
                        default=lambda self: self.env['ir.sequence'].next_by_code('nn.incoming.fund'))
    fund_account_id = fields.Many2one('nn.fund.account', string='Fund Account',
                                       required=True, tracking=True,
                                       )
    date = fields.Date(string='Date', required=True, default=fields.Date.today, tracking=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', related='fund_account_id.currency_id', store=True)
    transaction_ref = fields.Char(string='Transaction Reference', required=True, tracking=True)
    sender = fields.Char(string='Sender / Source', required=True)
    description = fields.Text(string='Description')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    _sql_constraints = [
        ('transaction_ref_account_unique',
         'UNIQUE(transaction_ref, fund_account_id)',
         'Transaction reference must be unique per fund account.')
    ]

    def action_confirm(self):
        for rec in self:
            if not self.env.user.has_group('nn_fund_management.group_fund_finance_user'):
                raise UserError('Only Finance Users can confirm incoming funds.')
            if rec.amount <= 0:
                raise UserError('Amount must be greater than zero.')
            rec.state = 'confirmed'
            rec.fund_account_id.sudo()._compute_balances()
            rec.message_post(body=f'Fund of {rec.amount} confirmed by {self.env.user.name}.')

    def action_cancel(self):
        for rec in self:
            if rec.state == 'confirmed':
                if not self.env.user.has_group('nn_fund_management.group_fund_administrator'):
                    raise UserError('Only Fund Administrators can cancel confirmed funds.')
            rec.state = 'cancelled'
            rec.fund_account_id.sudo()._compute_balances()

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError('Cannot delete a confirmed incoming fund. Please cancel it first.')
        return super().unlink()
