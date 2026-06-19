from odoo import models, fields, api
from odoo.exceptions import UserError


class ApprovalRule(models.Model):
    _name = 'nn.approval.rule'
    _description = 'Configurable Approval Rule'
    _order = 'sequence, min_amount'

    name = fields.Char(string='Rule Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)

    request_type = fields.Selection([
        ('allocation', 'Fund Allocation'),
        ('requisition', 'Fund Requisition'),
        ('transfer', 'Fund Transfer'),
        ('all', 'All Request Types'),
    ], string='Request Type', required=True, default='all')

    min_amount = fields.Monetary(string='Minimum Amount', required=True, default=0,
                                  currency_field='currency_id')
    max_amount = fields.Monetary(string='Maximum Amount', currency_field='currency_id',
                                  help='Leave 0 for no upper limit')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    project_category = fields.Selection([
        ('any', 'Any'),
        ('office_rent', 'Office Rent'),
        ('salary', 'Salary'),
        ('utility', 'Utility Expenses'),
        ('marketing', 'Marketing Expenses'),
        ('administrative', 'Administrative Expenses'),
    ], string='Expense Category', default='any')

    approval_line_ids = fields.One2many('nn.approval.rule.line', 'rule_id',
                                         string='Approval Sequence')

    @api.constrains('min_amount', 'max_amount')
    def _check_amount_range(self):
        for rec in self:
            if rec.max_amount and rec.max_amount <= rec.min_amount:
                raise UserError('Maximum amount must be greater than minimum amount.')

    @api.model
    def get_matching_rule(self, amount, request_type='all', company=None, category='any'):
        """Find the first matching rule for a given amount and request type."""
        company = company or self.env.company
        domain = [
            ('company_id', '=', company.id),
            ('active', '=', True),
            ('min_amount', '<=', amount),
            '|', ('request_type', '=', request_type), ('request_type', '=', 'all'),
        ]
        rules = self.search(domain, order='sequence, min_amount')
        for rule in rules:
            if rule.max_amount and amount > rule.max_amount:
                continue
            if rule.project_category != 'any' and category != 'any' and rule.project_category != category:
                continue
            return rule
        return self.env['nn.approval.rule']

    def get_approval_levels(self):
        """Returns ordered list of (level_code, approvers) for this rule."""
        self.ensure_one()
        return [(line.level_name, line.approver_ids | line.approver_group_id.users)
                for line in self.approval_line_ids.sorted('sequence')]


class ApprovalRuleLine(models.Model):
    _name = 'nn.approval.rule.line'
    _description = 'Approval Rule Line'
    _order = 'sequence'

    rule_id = fields.Many2one('nn.approval.rule', string='Rule', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Order', default=10)
    level_name = fields.Char(string='Level Name', required=True,
                              help='e.g. GM, Finance, MD')
    approver_ids = fields.Many2many('res.users', string='Specific Approvers')
    approver_group_id = fields.Many2one('res.groups', string='Or Approver Group')

    @api.constrains('approver_ids', 'approver_group_id')
    def _check_has_approver(self):
        for rec in self:
            if not rec.approver_ids and not rec.approver_group_id:
                raise UserError(
                    f'Approval line "{rec.level_name}" must have at least one '
                    f'approver user or approver group.'
                )
