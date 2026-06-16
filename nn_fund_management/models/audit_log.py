from odoo import models, fields


class AuditLog(models.Model):
    _name = 'nn.audit.log'
    _description = 'Fund Audit Log'
    _order = 'date desc'

    name = fields.Char(string='Action', required=True)
    date = fields.Datetime(string='Date & Time', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    model_name = fields.Char(string='Document Type')
    record_ref = fields.Char(string='Document Reference')
    previous_state = fields.Char(string='Previous Status')
    new_state = fields.Char(string='New Status')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    fund_account_id = fields.Many2one('nn.fund.account', string='Fund Account')
    project_id = fields.Many2one('nn.fund.project', string='Project')
    expense_head_id = fields.Many2one('nn.expense.head', string='Expense Head')
    comment = fields.Text(string='Comment / Notes')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
