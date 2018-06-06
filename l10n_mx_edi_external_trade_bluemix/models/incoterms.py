# -*- coding: utf-8 -*-

from odoo import fields, models, api


class Incoterms(models.Model):
    _name = "l10n.mx.edi.external.incoterms"
    _description = "Incoterms"

    name = fields.Char(
        'Name', required=True, translate=True,
        help="Incoterms are series of sales terms. They are used to divide transaction costs and responsibilities between buyer and seller and reflect state-of-the-art transportation practices.")
    code = fields.Char(
        'Code', size=3, required=True,
        help="Incoterm Standard Code")
    active = fields.Boolean(
        'Active', default=True,
        help="By unchecking the active field, you may hide an INCOTERM you will not use.")

    @api.multi
    def name_get(self):
        result = []
        for prod in self:
            result.append((prod.id, "%s - %s" % (prod.code, prod.name or '')))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain_name = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        recs = self.search(domain_name + args, limit=limit)
        return recs.name_get()