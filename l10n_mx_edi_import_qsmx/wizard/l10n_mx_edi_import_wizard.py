# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _


class EdiImport(models.TransientModel):
    _inherit = 'l10n.mx.edi.import.wizard'

    def get_invoice_line_values_from_line(self, line):
        vals = super(EdiImport, self).get_invoice_line_values_from_line(line)

        split = line.product_code.split('{=}')

        vals['client_identification_number'] = split[1] if len(split) == 2 else split[0]
        return vals


class EdiImportLine(models.TransientModel):
    _inherit = 'l10n.mx.edi.import.wizard.line'

    def product_lookup(self):
        if self.product_code:

            split = self.product_code.split('{=}')

            if split[0]:
                product = self.env['product.product'].search([('default_code', '=', self.product_code)])

                return product

        return False