import uuid
from odoo import models, fields, api


class BankEmailTestWizard(models.TransientModel):
    """Lets a user paste sample bank notification email text and see the
    parser run end-to-end, without needing a live mailbox. Useful for the
    demo video and for testing the parser logic."""
    _name = 'nn.bank.email.test.wizard'
    _description = 'Test Bank Email Parser'

    fund_account_id = fields.Many2one('nn.fund.account', string='Fund Account', required=True)
    subject = fields.Char(string='Email Subject', default='Transaction Alert')
    sender = fields.Char(string='From', default='alerts@examplebank.com')
    body = fields.Text(string='Email Body', required=True, default=(
        'Dear Customer,\n\n'
        'An amount of BDT 50,000.00 has been credited to your account.\n'
        'A/C No: XXXX-XXXX-4521\n'
        'Transaction Reference: TXN20260617001\n'
        'From: Example Bank Ltd.\n\n'
        'Thank you for banking with us.'
    ))
    result_message = fields.Text(string='Result', readonly=True)

    def action_run_parser(self):
        self.ensure_one()
        msg_id = f'test-{uuid.uuid4()}@manual-test'
        log = self.env['nn.bank.email.parser'].process_incoming_email(
            message_id=msg_id,
            subject=self.subject,
            body=self.body,
            sender=self.sender,
            fund_account_id=self.fund_account_id.id,
        )
        if log.status == 'parsed':
            msg = (f'Parsed successfully.\n'
                   f'Bank: {log.bank_name}\n'
                   f'Amount: {log.received_amount}\n'
                   f'Reference: {log.transaction_ref}\n'
                   f'Created Incoming Fund: {log.incoming_fund_id.name}')
        elif log.status == 'duplicate':
            msg = f'Duplicate transaction detected: {log.error_message}'
        else:
            msg = f'Parsing failed: {log.error_message}'

        self.result_message = msg
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nn.bank.email.test.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
