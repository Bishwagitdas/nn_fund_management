from odoo import models, fields


class ApprovalHistory(models.Model):
    _name = 'nn.approval.history'
    _description = 'Approval History'
    _order = 'date desc'

    name = fields.Char(string='Description', compute='_compute_name', store=True)
    model_name = fields.Char(string='Related Model')
    record_id = fields.Integer(string='Record ID')
    approval_level = fields.Selection([
        ('gm', 'General Manager'),
        ('md', 'Managing Director'),
    ], string='Approval Level', required=True)
    approver_id = fields.Many2one('res.users', string='Approver', required=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True)
    comment = fields.Text(string='Comment')
    result = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Result', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    previous_state = fields.Char(string='Previous State')
    new_state = fields.Char(string='New State')

    # Polymorphic links
    allocation_id = fields.Many2one('nn.fund.allocation', string='Allocation', ondelete='cascade')
    requisition_id = fields.Many2one('nn.fund.requisition', string='Requisition', ondelete='cascade')
    transfer_id = fields.Many2one('nn.fund.transfer', string='Transfer', ondelete='cascade')

    def _compute_name(self):
        for rec in self:
            level = dict(self._fields['approval_level'].selection).get(rec.approval_level, '')
            result = dict(self._fields['result'].selection).get(rec.result, '')
            rec.name = f'{level} - {result}'
