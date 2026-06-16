from odoo import models, fields


class FundConfig(models.Model):
    _name = 'nn.fund.config'
    _description = 'Fund Management Configuration'

    name = fields.Char(string='Configuration Name', required=True, default='Default')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                  default=lambda self: self.env.company)
    gm_approver_ids = fields.Many2many(
        'res.users', 'fund_config_gm_rel', 'config_id', 'user_id',
        string='GM Approvers',
        domain="[('groups_id.name', 'like', 'GM Approver')]"
    )
    md_approver_ids = fields.Many2many(
        'res.users', 'fund_config_md_rel', 'config_id', 'user_id',
        string='MD Approvers',
        domain="[('groups_id.name', 'like', 'MD Approver')]"
    )

    _sql_constraints = [
        ('company_unique', 'UNIQUE(company_id)', 'Only one configuration per company is allowed.')
    ]
