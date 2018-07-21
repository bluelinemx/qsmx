# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_mx_customs_tax_fraction_id = fields.Many2one('l10n.mx.edi.external.customs.tax.fraction', string='Customs Tax Fraction')
    l10n_mx_customs_uom_id = fields.Many2one('l10n.mx.edi.external.customs.uom', string='Customs UoM', related='l10n_mx_customs_tax_fraction_id.customs_uom_id', store=True, change_default=True)

    #//ComercioExterior/Mercancias/DescripcionesEspecificas
    l10n_mx_brand = fields.Char('Brand', default='')
    l10n_mx_brand_required = fields.Boolean('Brand Required')
    l10n_mx_model = fields.Char('Model', default='')
    l10n_mx_sub_model = fields.Char('Sub Model', default='')
    l10n_mx_serial_no = fields.Char('Serial No', default='')

    @api.onchange('l10n_mx_customs_tax_fraction_id')
    def _onchange_customs_tax_fraction_id(self):
        self.l10n_mx_customs_uom_id = self.l10n_mx_customs_tax_fraction_id.customs_uom_id.id if self.l10n_mx_customs_tax_fraction_id.id else False

    @api.onchange('l10n_mx_model', 'l10n_mx_sub_model', 'l10n_mx_serial_no')
    def _onchange_l10n_mx_model_required(self):
        self.l10n_mx_brand_required = True if (
        self.l10n_mx_model or self.l10n_mx_sub_model or self.l10n_mx_serial_no) else False

