# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _


class EdiImport(models.TransientModel):
    _inherit = 'l10n.mx.edi.import.wizard'

    def get_invoice_line_values_from_line(self, line):
        vals = super(EdiImport, self).get_invoice_line_values_from_line(line)
        vals['client_identification_number'] = line.product_code