from odoo import models, fields, api
from odoo.exceptions import UserError


class ApprovalMixin(models.AbstractModel):
    _name = 'nn.approval.mixin'
    _description = 'Approval Workflow Mixin'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    requested_by = fields.Many2one('res.users', string='Requested By',
                                    default=lambda self: self.env.user, tracking=True)
    submitted_by = fields.Many2one('res.users', string='Submitted By', tracking=True, copy=False)
    submitted_date = fields.Datetime(string='Submitted Date', copy=False)
    gm_approver_id = fields.Many2one('res.users', string='GM Approver', tracking=True, copy=False)
    gm_approved_date = fields.Datetime(string='GM Approved Date', copy=False)
    md_approver_id = fields.Many2one('res.users', string='MD Approver', tracking=True, copy=False)
    md_approved_date = fields.Datetime(string='MD Approved Date', copy=False)
    rejection_reason = fields.Text(string='Rejection Reason', copy=False)
    approval_history_ids = fields.One2many('nn.approval.history', compute='_compute_approval_history')

    def _compute_approval_history(self):
        History = self.env['nn.approval.history']
        for rec in self:
            field_name = self._get_history_field()
            rec.approval_history_ids = History.search([(field_name, '=', rec.id)])

    def _get_history_field(self):
        mapping = {
            'nn.fund.allocation': 'allocation_id',
            'nn.fund.requisition': 'requisition_id',
            'nn.fund.transfer': 'transfer_id',
        }
        return mapping.get(self._name, 'allocation_id')

    def _get_fund_config(self):
        config = self.env['nn.fund.config'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            raise UserError('Please configure Fund Management settings for your company first.')
        return config

    def _log_approval(self, level, result, comment='', prev_state='', new_state=''):
        field_name = self._get_history_field()
        vals = {
            'approval_level': level,
            'approver_id': self.env.user.id,
            'date': fields.Datetime.now(),
            'comment': comment,
            'result': result,
            'amount': getattr(self, 'amount', 0),
            'previous_state': prev_state,
            'new_state': new_state,
            field_name: self.id,
        }
        self.env['nn.approval.history'].create(vals)

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft records can be submitted.')
            rec._validate_before_submit()
            prev = rec.state
            rec.state = 'submitted'
            rec.submitted_by = self.env.user
            rec.submitted_date = fields.Datetime.now()
            rec._on_submit()
            rec.message_post(body=f'Request submitted by {self.env.user.name}.')
            rec._notify_approvers('gm')

    def action_approve_gm(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError('Record must be in Submitted state for GM approval.')
            config = rec._get_fund_config()
            if self.env.user not in config.gm_approver_ids:
                raise UserError('You are not authorized as a GM Approver.')
            if self.env.user == rec.requested_by:
                raise UserError('You cannot approve your own request.')
            prev = rec.state
            rec.state = 'gm_approved'
            rec.gm_approver_id = self.env.user
            rec.gm_approved_date = fields.Datetime.now()
            rec._log_approval('gm', 'approved', prev_state=prev, new_state=rec.state)
            rec.message_post(body=f'GM approval granted by {self.env.user.name}.')
            rec._notify_approvers('md')

    def action_approve_md(self):
        for rec in self:
            if rec.state != 'gm_approved':
                raise UserError('GM must approve before MD approval.')
            config = rec._get_fund_config()
            if self.env.user not in config.md_approver_ids:
                raise UserError('You are not authorized as an MD Approver.')
            if self.env.user == rec.requested_by:
                raise UserError('You cannot approve your own request.')
            prev = rec.state
            rec.state = 'approved'
            rec.md_approver_id = self.env.user
            rec.md_approved_date = fields.Datetime.now()
            rec._log_approval('md', 'approved', prev_state=prev, new_state=rec.state)
            rec._on_approve()
            rec.message_post(body=f'MD approval granted by {self.env.user.name}. Request fully approved.')

    def action_reject(self):
        for rec in self:
            if rec.state not in ('submitted', 'gm_approved'):
                raise UserError('Only submitted or GM-approved records can be rejected.')
            prev = rec.state
            level = 'gm' if rec.state == 'submitted' else 'md'
            rec._on_reject()
            rec.state = 'rejected'
            rec._log_approval(level, 'rejected', prev_state=prev, new_state='rejected')
            rec.message_post(body=f'Request rejected by {self.env.user.name}.')

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                if not self.env.user.has_group('nn_fund_management.group_fund_administrator'):
                    raise UserError('Only Fund Administrators can cancel approved records.')
            if rec.state in ('rejected', 'cancelled'):
                raise UserError('Record is already rejected or cancelled.')
            rec._on_cancel()
            rec.state = 'cancelled'
            rec.message_post(body=f'Request cancelled by {self.env.user.name}.')

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError('Only rejected or cancelled records can be reset to draft.')
            rec.state = 'draft'

    # ---- hooks for child models to override ----
    def _validate_before_submit(self):
        pass

    def _on_submit(self):
        pass

    def _on_approve(self):
        pass

    def _on_reject(self):
        pass

    def _on_cancel(self):
        pass

    def _notify_approvers(self, level):
        config = self.env['nn.fund.config'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            return
        approvers = config.gm_approver_ids if level == 'gm' else config.md_approver_ids
        for approver in approvers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=approver.id,
                summary=f'Approval required: {self.display_name}',
                note=f'Please review and approve this {self._description}.',
            )

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'rejected', 'cancelled'):
                raise UserError('Cannot delete records that are not in draft, rejected or cancelled state.')
        return super().unlink()
