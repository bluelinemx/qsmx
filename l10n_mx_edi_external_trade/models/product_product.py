# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_mx_customs_tax_fraction_id = fields.Many2one('l10n.mx.edi.external.customs.tax.fraction', string='Customs Tax Fraction')
    l10n_mx_customs_uom_id = fields.Many2one('l10n.mx.edi.external.customs.uom', string='Customs UoM', related='l10n_mx_customs_tax_fraction_id.customs_uom_id')

