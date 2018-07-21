# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from functools import partial


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.model_cr
    def init(self):
        if 'client_identification_number_backup' in self._fields and 'client_identification_number' in self._fields:
            try:
                self._cr.execute('UPDATE account_invoice_line SET client_identification_number=client_identification_number_backup WHERE not client_identification_number_backup ISNULL')
            except:
                pass
