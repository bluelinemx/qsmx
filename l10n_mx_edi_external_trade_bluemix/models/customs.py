# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CustomsUom(models.Model):
    _name = 'l10n.mx.edi.external.customs.uom'
    _order = 'code,name'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)

    uom_id = fields.Many2one('product.uom', string='Product UoM')

    active = fields.Boolean(
        help='If this record is not active, this cannot be selected.',
        default=True)

    @api.multi
    def name_get(self):
        result = []
        for prod in self:
            result.append((prod.id, "%s %s" % (prod.code, prod.name or '')))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain_name = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        recs = self.search(domain_name + args, limit=limit)
        return recs.name_get()


class CustomsTaxFraction(models.Model):
    _name = 'l10n.mx.edi.external.customs.tax.fraction'
    _order = 'code,name'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)

    availability_start_date = fields.Date(string='Start Date')
    availability_end_date = fields.Date(string='End Date')

    customs_uom_id = fields.Many2one('l10n.mx.edi.external.customs.uom', string='Customs UoM')

    purchase_tax_id = fields.Many2one('account.tax', string='Purchase Tax (Import)')
    sale_tax_id = fields.Many2one('account.tax', string='Sale Tax (Export)')
    active = fields.Boolean(
        help='If this record is not active, this cannot be selected.',
        default=True)

    @api.multi
    def name_get(self):
        result = []
        for prod in self:
            result.append((prod.id, "%s %s" % (prod.code, prod.name or '')))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain_name = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        recs = self.search(domain_name + args, limit=limit)
        return recs.name_get()