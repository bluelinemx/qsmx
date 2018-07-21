# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from functools import partial


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    client_identification_number_backup = fields.Char('No. Identification')

    @api.model_cr
    def init(self):
        if 'client_identification_number_backup' in self._fields and 'client_identification_number' in self._fields:
            try:
                self._cr.execute('UPDATE account_invoice_line SET client_identification_number_backup=client_identification_number WHERE not client_identification_number ISNULL')
            except:
                pass
