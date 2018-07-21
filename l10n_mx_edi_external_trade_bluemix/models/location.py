# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CountryStateZipCode(models.Model):
    _name = 'l10n.mx.edi.country.state.zipcode'
    _description = 'Country State ZipCodes'

    code = fields.Char('Zip', required=True)
    country_id = fields.Many2one('res.country', related='country_state_id.country_id', string='Country', store=True)
    country_state_id = fields.Many2one('res.country.state', string='Country State', required=True)
    municipality_id = fields.Many2one('res.country.state.municipality', string='Municipality')
    locality_id = fields.Many2one('res.country.state.locality', string='Locality')


class CountryState(models.Model):
    _inherit = 'res.country.state'

    l10n_mx_edi_zip_ids = fields.One2many('l10n.mx.edi.country.state.zipcode', 'country_state_id', string='Zip Codes')


class Locality(models.Model):
    _name = 'res.country.state.locality'
    _description = 'Locality'
    _order = 'name'

    country_state_id = fields.Many2one('res.country.state', string='Country State', required=True)
    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)
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


class Municipality(models.Model):
    _name = 'res.country.state.municipality'
    _description = 'Municipality'
    _order = 'name'

    country_state_id = fields.Many2one('res.country.state', string='Country State', required=True)
    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Name', required=True)
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


class Colony(models.Model):
    _name = 'res.country.colony'
    _description = 'Colony'
    _order = 'name'

    country_id = fields.Many2one('res.country', string='Country', required=True)
    code = fields.Char(string='Code')
    zip = fields.Char('Zip')
    name = fields.Char(string='Name')
    active = fields.Boolean(
        help='If this record is not active, this cannot be selected.',
        default=True)

    @api.multi
    def name_get(self):
        result = []
        for prod in self:
            result.append((prod.id, "%s %s (CP %s)" % (prod.code, prod.name or '', prod.zip)))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain_name = ['|', ('zip', '=', name), '|', ('name', 'ilike', name), ('code', 'ilike', name)]
        recs = self.search(domain_name + args, limit=limit)
        return recs.name_get()
