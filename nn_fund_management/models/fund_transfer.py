from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class FundTransfer(models.Model):
    _name = 'nn.fund.transfer'
    _description = 'Fund Transfer'
    _inherit = ['nn.approval.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(string='Transfer Number', required=True, copy=False,
                        default=lambda self: self.env['ir.sequence'].next_by_code('nn.fund.transfer'))
    transfer_type = fields.Selection([
        ('project_project', 'Project → Project'),
        ('project_expense', 'Project → Expense Head'),
        ('expense_project', 'Expense Head → Project'),
        ('expense_expense', 'Expense Head → Expense Head'),
    ], string='Transfer Type', required=True, default='project_project', tracking=True)

    # Source
    source_project_id = fields.Many2one('nn.fund.project', string='Source Project', tracking=True)
    source_expense_head_id = fields.Many2one('nn.expense.head', string='Source Expense Head', tracking=True)

    # Destination
    destination_project_id = fields.Many2one('nn.fund.project', string='Destination Project', tracking=True)
    destination_expense_head_id = fields.Many2one('nn.expense.head', string='Destination Expense Head', tracking=True)

    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    reason = fields.Text(string='Reason', required=True)
    request_date = fields.Date(string='Request Date', required=True, default=fields.Date.today)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    @api.constrains('source_project_id', 'source_expense_head_id',
                    'destination_project_id', 'destination_expense_head_id', 'transfer_type')
    def _check_transfer_fields(self):
        for rec in self:
            if rec.transfer_type == 'project_project':
                if not rec.source_project_id or not rec.destination_project_id:
                    raise ValidationError('Please select source and destination projects.')
                if rec.source_project_id == rec.destination_project_id:
                    raise ValidationError('Source and destination cannot be the same project.')
            elif rec.transfer_type == 'project_expense':
                if not rec.source_project_id or not rec.destination_expense_head_id:
                    raise ValidationError('Please select source project and destination expense head.')
            elif rec.transfer_type == 'expense_project':
                if not rec.source_expense_head_id or not rec.destination_project_id:
                    raise ValidationError('Please select source expense head and destination project.')
            elif rec.transfer_type == 'expense_expense':
                if not rec.source_expense_head_id or not rec.destination_expense_head_id:
                    raise ValidationError('Please select source and destination expense heads.')
                if rec.source_expense_head_id == rec.destination_expense_head_id:
                    raise ValidationError('Source and destination cannot be the same expense head.')

    def _get_source_balance(self):
        if self.transfer_type in ('project_project', 'project_expense'):
            self.source_project_id._compute_balances()
            return self.source_project_id.available_fund, self.source_project_id.name
        else:
            self.source_expense_head_id._compute_balances()
            return self.source_expense_head_id.available_fund, self.source_expense_head_id.name

    def _validate_before_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError('Transfer amount must be greater than zero.')
            available, source_name = rec._get_source_balance()
            if available < rec.amount:
                raise UserError(
                    f'Insufficient available balance in "{source_name}". '
                    f'Available: {available:.2f}, Requested: {rec.amount:.2f}'
                )

    def _refresh_all_balances(self):
        for f in [self.source_project_id, self.source_expense_head_id,
                  self.destination_project_id, self.destination_expense_head_id]:
            if f:
                f._compute_balances()

    def _on_submit(self):
        self._refresh_all_balances()

    def _on_approve(self):
        self._refresh_all_balances()

    def _on_reject(self):
        self._refresh_all_balances()

    def _on_cancel(self):
        self._refresh_all_balances()
