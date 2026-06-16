from odoo import models, fields, api


class FundAccount(models.Model):
    _name = 'nn.fund.account'
    _description = 'Fund Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Account Name', required=True, tracking=True)
    code = fields.Char(string='Account Code')
    account_type = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ], string='Account Type', required=True, default='bank', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    # Computed balance fields
    total_received = fields.Monetary(string='Total Received', compute='_compute_balances',
                                      store=True, currency_field='currency_id')
    unassigned_balance = fields.Monetary(string='Unassigned Balance', compute='_compute_balances',
                                          store=True, currency_field='currency_id')
    on_hold_amount = fields.Monetary(string='On Hold', compute='_compute_balances',
                                      store=True, currency_field='currency_id')
    total_assigned = fields.Monetary(string='Total Assigned', compute='_compute_balances',
                                      store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.company.currency_id)

    incoming_fund_ids = fields.One2many('nn.incoming.fund', 'fund_account_id', string='Incoming Funds')
    allocation_ids = fields.One2many('nn.fund.allocation', 'fund_account_id', string='Allocations')

    @api.depends(
        'incoming_fund_ids.amount', 'incoming_fund_ids.state',
        'allocation_ids.amount', 'allocation_ids.state',
    )
    def _compute_balances(self):
        for rec in self:
            confirmed_funds = rec.incoming_fund_ids.filtered(lambda f: f.state == 'confirmed')
            rec.total_received = sum(confirmed_funds.mapped('amount'))

            alloc = rec.allocation_ids
            on_hold = sum(alloc.filtered(lambda a: a.state == 'submitted').mapped('amount'))
            on_hold += sum(alloc.filtered(lambda a: a.state == 'gm_approved').mapped('amount'))
            assigned = sum(alloc.filtered(lambda a: a.state == 'approved').mapped('amount'))
            rejected_cancelled = sum(alloc.filtered(
                lambda a: a.state in ('rejected', 'cancelled')).mapped('amount'))

            rec.on_hold_amount = on_hold
            rec.total_assigned = assigned
            rec.unassigned_balance = rec.total_received - on_hold - assigned
