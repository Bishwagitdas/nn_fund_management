from odoo import models, fields, api


class FundDashboard(models.TransientModel):
    """Transient model backing the dashboard view. Each open recomputes
    fresh KPI numbers from live data - nothing is stored."""
    _name = 'nn.fund.dashboard'
    _description = 'Fund Management Dashboard'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    total_received = fields.Monetary(string='Total Funds Received', currency_field='currency_id')
    total_unassigned = fields.Monetary(string='Unassigned Balance', currency_field='currency_id')
    total_on_hold = fields.Monetary(string='Total On Hold', currency_field='currency_id')
    total_assigned = fields.Monetary(string='Total Assigned', currency_field='currency_id')
    total_spent = fields.Monetary(string='Total Spent', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    pending_allocations = fields.Integer(string='Pending Allocations')
    pending_requisitions = fields.Integer(string='Pending Requisitions')
    pending_transfers = fields.Integer(string='Pending Transfers')
    total_pending_approvals = fields.Integer(string='Total Pending Approvals',
                                              compute='_compute_total_pending')

    @api.depends('pending_allocations', 'pending_requisitions', 'pending_transfers')
    def _compute_total_pending(self):
        for rec in self:
            rec.total_pending_approvals = (rec.pending_allocations
                                            + rec.pending_requisitions
                                            + rec.pending_transfers)

    project_balance_ids = fields.One2many('nn.fund.project', compute='_compute_projects')
    expense_balance_ids = fields.One2many('nn.expense.head', compute='_compute_expenses')

    def _compute_projects(self):
        for rec in self:
            rec.project_balance_ids = self.env['nn.fund.project'].search(
                [('company_id', '=', rec.company_id.id)])

    def _compute_expenses(self):
        for rec in self:
            rec.expense_balance_ids = self.env['nn.expense.head'].search(
                [('company_id', '=', rec.company_id.id)])

    @api.model
    def get_dashboard_data(self):
        """Returns a fresh dashboard record with computed KPIs."""
        company = self.env.company
        accounts = self.env['nn.fund.account'].search([('company_id', '=', company.id)])

        pending_alloc = self.env['nn.fund.allocation'].search_count([
            ('company_id', '=', company.id),
            ('state', 'in', ('submitted', 'gm_approved')),
        ])
        pending_req = self.env['nn.fund.requisition'].search_count([
            ('company_id', '=', company.id),
            ('state', 'in', ('submitted', 'gm_approved')),
        ])
        pending_trf = self.env['nn.fund.transfer'].search_count([
            ('company_id', '=', company.id),
            ('state', 'in', ('submitted', 'gm_approved')),
        ])

        projects = self.env['nn.fund.project'].search([('company_id', '=', company.id)])
        total_spent = sum(projects.mapped('total_spent'))
        expense_heads = self.env['nn.expense.head'].search([('company_id', '=', company.id)])
        total_spent += sum(expense_heads.mapped('total_spent'))

        return self.create({
            'company_id': company.id,
            'total_received': sum(accounts.mapped('total_received')),
            'total_unassigned': sum(accounts.mapped('unassigned_balance')),
            'total_on_hold': sum(accounts.mapped('on_hold_amount')),
            'total_assigned': sum(accounts.mapped('total_assigned')),
            'total_spent': total_spent,
            'pending_allocations': pending_alloc,
            'pending_requisitions': pending_req,
            'pending_transfers': pending_trf,
        })

    def action_refresh(self):
        self.ensure_one()
        fresh = self.get_dashboard_data()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nn.fund.dashboard',
            'res_id': fresh.id,
            'view_mode': 'form',
            'target': 'current',
        }
