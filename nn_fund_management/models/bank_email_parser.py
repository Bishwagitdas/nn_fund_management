import re
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class BankEmailLog(models.Model):
    _name = 'nn.bank.email.log'
    _description = 'Bank Email Processing Log'
    _order = 'received_date desc'

    name = fields.Char(string='Subject', required=True)
    message_id = fields.Char(string='Email Message-ID', required=True, index=True)
    received_date = fields.Datetime(string='Received Date', default=fields.Datetime.now)
    status = fields.Selection([
        ('parsed', 'Parsed Successfully'),
        ('failed', 'Failed to Parse'),
        ('duplicate', 'Duplicate Email'),
    ], string='Status', required=True, default='failed')

    bank_name = fields.Char(string='Bank Name')
    account_number_masked = fields.Char(string='Account Number (Masked)')
    transaction_ref = fields.Char(string='Transaction Reference')
    received_amount = fields.Float(string='Received Amount')
    sender_info = fields.Char(string='Sender Info')

    raw_body = fields.Text(string='Raw Email Body')
    error_message = fields.Text(string='Error / Failure Reason')
    incoming_fund_id = fields.Many2one('nn.incoming.fund', string='Created Incoming Fund')

    _sql_constraints = [
        ('message_id_unique', 'UNIQUE(message_id)',
         'This email has already been processed (duplicate Message-ID).')
    ]


class BankEmailParser(models.AbstractModel):
    """Prototype parser that extracts fund transaction details from bank
    notification email text. Real bank credentials are NEVER stored in
    source code - a live mailbox would be configured through Odoo's
    standard fetchmail.server model (Settings > Technical > Email >
    Incoming Mail Servers), which encrypts credentials in the database."""
    _name = 'nn.bank.email.parser'
    _description = 'Bank Email Parser (Prototype)'

    AMOUNT_PATTERNS = [
        r'(?:amount|credited|received)[:\s]+(?:BDT|USD|Tk\.?|\$)?\s*([\d,]+\.?\d*)',
        r'(?:BDT|USD|Tk\.?|\$)\s*([\d,]+\.?\d*)\s*(?:has been|was)?\s*(?:credited|received)',
    ]
    REF_PATTERNS = [
        r'(?:transaction|txn|ref(?:erence)?)\s*(?:id|no\.?|number)?[:\s]+([A-Za-z0-9\-/]+)',
    ]
    ACCOUNT_PATTERNS = [
        r'(?:a/c|account)\s*(?:no\.?)?[:\s]+([X\d\*]+\d{4})',
    ]
    BANK_NAME_PATTERNS = [
        r'(?:from|via)\s+([A-Z][A-Za-z\s]+(?:Bank|Ltd\.?))',
    ]

    @api.model
    def parse_email_body(self, body, sender='', subject=''):
        """Parse a bank notification email body. Returns a dict with
        extracted fields, or raises ValueError if amount/reference cannot
        be determined."""
        result = {
            'bank_name': self._extract(self.BANK_NAME_PATTERNS, body),
            'account_number_masked': self._extract(self.ACCOUNT_PATTERNS, body),
            'transaction_ref': self._extract(self.REF_PATTERNS, body),
            'received_amount': self._extract_amount(body),
            'sender_info': sender,
        }
        if not result['received_amount']:
            raise ValueError('Could not detect a transaction amount in the email body.')
        if not result['transaction_ref']:
            raise ValueError('Could not detect a transaction reference in the email body.')
        return result

    def _extract(self, patterns, text):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return False

    def _extract_amount(self, text):
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(',', '')
                try:
                    return float(raw)
                except ValueError:
                    continue
        return False

    @api.model
    def process_incoming_email(self, message_id, subject, body, sender,
                                fund_account_id=False, received_date=None):
        """Main entry point: process one bank email and create a Pending
        Verification incoming fund record if parsing succeeds.
        Deduplicates by message_id and by transaction reference."""
        Log = self.env['nn.bank.email.log']

        existing = Log.search([('message_id', '=', message_id)], limit=1)
        if existing:
            _logger.info('Bank email %s already processed, skipping.', message_id)
            return existing

        log_vals = {
            'name': subject or 'Bank Notification',
            'message_id': message_id,
            'received_date': received_date or fields.Datetime.now(),
            'raw_body': body,
            'sender_info': sender,
            'status': 'failed',
        }

        try:
            parsed = self.parse_email_body(body, sender=sender, subject=subject)
            log_vals.update({
                'bank_name': parsed.get('bank_name') or 'Unknown Bank',
                'account_number_masked': parsed.get('account_number_masked'),
                'transaction_ref': parsed['transaction_ref'],
                'received_amount': parsed['received_amount'],
                'status': 'parsed',
            })

            if not fund_account_id:
                fund_account_id = self.env['nn.fund.account'].search(
                    [('company_id', '=', self.env.company.id)], limit=1).id
            if not fund_account_id:
                raise ValueError('No Fund Account configured to attach this transaction to.')

            duplicate_ref = self.env['nn.incoming.fund'].search([
                ('fund_account_id', '=', fund_account_id),
                ('transaction_ref', '=', parsed['transaction_ref']),
            ], limit=1)
            if duplicate_ref:
                log_vals['status'] = 'duplicate'
                log_vals['error_message'] = (
                    f"Transaction reference {parsed['transaction_ref']} already exists "
                    f"as incoming fund {duplicate_ref.name}."
                )
                log = Log.create(log_vals)
                return log

            fund = self.env['nn.incoming.fund'].create({
                'fund_account_id': fund_account_id,
                'date': fields.Date.today(),
                'amount': parsed['received_amount'],
                'transaction_ref': parsed['transaction_ref'],
                'sender': parsed.get('bank_name') or sender or 'Bank Email',
                'description': f"Auto-created from bank email. Account: {parsed.get('account_number_masked') or 'N/A'}",
                'state': 'draft',
            })
            fund.message_post(
                body='This record was auto-created from a bank notification email '
                     'and is Pending Verification (Draft). A Finance User must '
                     'review and confirm it.'
            )
            log_vals['incoming_fund_id'] = fund.id
            log = Log.create(log_vals)
            return log

        except ValueError as e:
            log_vals['error_message'] = str(e)
            log = Log.create(log_vals)
            _logger.warning('Failed to parse bank email %s: %s', message_id, e)
            return log
        except Exception as e:
            log_vals['error_message'] = f'Unexpected error: {e}'
            log = Log.create(log_vals)
            _logger.exception('Unexpected error processing bank email %s', message_id)
            return log
