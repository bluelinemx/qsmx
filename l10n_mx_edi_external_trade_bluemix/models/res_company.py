# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api, _
import logging

from odoo.exceptions import ValidationError
from ..hooks import _load_xsd_complement

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_trusted_exporter_number = fields.Char(string='Trusted Exporter Number')

    l10n_mx_edi_locality_id = fields.Many2one('res.country.state.locality', compute='_compute_address',
                                              inverse='_inverse_locality', string='Location')
    l10n_mx_edi_colony_id = fields.Many2one('res.country.colony', compute='_compute_address', inverse='_inverse_colony',
                                            string='Colony')
    l10n_mx_edi_municipality_id = fields.Many2one('res.country.state.municipality', compute='_compute_address',
                                                  inverse='_inverse_municipality', string='Municipality')
    l10n_mx_edi_extra_location_fields = fields.Boolean(compute='_compute_show_extra_location_fields')

    def _get_company_address_fields(self, partner):
        vals = super(ResCompany, self)._get_company_address_fields(partner)

        vals.update({
            'l10n_mx_edi_locality_id': partner.l10n_mx_edi_locality_id,
            'l10n_mx_edi_colony_id': partner.l10n_mx_edi_colony_id,
            'l10n_mx_edi_municipality_id': partner.l10n_mx_edi_municipality_id,
        })

        return vals

    def _inverse_locality(self):
        for company in self:
            company.partner_id.l10n_mx_edi_locality_id = company.l10n_mx_edi_locality_id

    def _inverse_colony(self):
        for company in self:
            company.partner_id.l10n_mx_edi_colony_id = company.l10n_mx_edi_colony_id

    def _inverse_municipality(self):
        for company in self:
            company.partner_id.l10n_mx_edi_municipality_id = company.l10n_mx_edi_municipality_id

    @api.onchange('l10n_mx_edi_municipality_id')
    def onchange_l10n_mx_edi_municipality_id(self):
        pass

    @api.onchange('l10n_mx_edi_locality_id')
    def onchange_l10n_mx_edi_locality_id(self):
        self.l10n_mx_edi_locality = self.l10n_mx_edi_locality_id.name if self.l10n_mx_edi_locality_id.id else None

    @api.onchange('l10n_mx_edi_colony_id')
    def onchange_l10n_mx_edi_colony_id(self):
        self.l10n_mx_edi_colony = self.l10n_mx_edi_colony_id.name if self.l10n_mx_edi_colony_id.id else None

        if self.l10n_mx_edi_colony_id.id:
            self.zip = self.l10n_mx_edi_colony_id.zip


    # @api.onchange('zip', 'state_id', 'country_id', 'l10n_mx_edi_municipality_id', 'l10n_mx_edi_municipality_id', 'l10n_mx_edi_colony_id')
    def _compute_onchange_l10n_mx_domain(self, field=None, value=None):

        search_domain = []

        if self.country_id.id:
            search_domain.append(('country_id', '=', self.country_id.id))

        if self.state_id.id:
            search_domain.append(('country_state_id', '=', self.state_id.id))

        if self.zip:
            search_domain.append(('code', '=', self.zip))

        if self.l10n_mx_edi_municipality_id.id:
            search_domain.append(('municipality_id', '=', self.l10n_mx_edi_municipality_id.id))

        if self.l10n_mx_edi_locality_id.id:
            search_domain.append(('locality_id', '=', self.l10n_mx_edi_locality_id.id))

        items = self.env['l10n.mx.edi.country.state.zipcode'].sudo().search(search_domain)

        if len(items) == 0:
            raise ValidationError(_('The current combination of address fields are not valid.'))

        filtered_ids = dict(state=[], locality=[], municipality=[], zip=[])

        for row in items:
            if row.municipality_id.id:
                filtered_ids['municipality'].append(row.municipality_id.id)

            if row.locality_id.id:
                filtered_ids['locality'].append(row.locality_id.id)

            if row.country_state_id.id:
                filtered_ids['state'].append(row.country_state_id.id)

            if row.code:
                filtered_ids['zip'].append(row.code)

        if len(filtered_ids['municipality']) == 1:
            self.l10n_mx_edi_municipality_id = filtered_ids['municipality'][0]

            if not self.state_id.id:
                self.state_id = self.l10n_mx_edi_municipality_id.country_state_id.id

        if len(filtered_ids['locality']) == 1:
            self.l10n_mx_edi_locality_id = filtered_ids['locality'][0]
        elif self.l10n_mx_edi_locality_id.id and self.l10n_mx_edi_locality_id.id not in filtered_ids['locality']:
            self.l10n_mx_edi_locality_id = False

        if len(filtered_ids['state']) == 1:
            self.state_id = filtered_ids['state'][0]
        elif self.state_id.id and self.state_id.id not in filtered_ids['state']:
            self.state_id = False

        domain = {
            'l10n_mx_edi_colony_id': [('zip', 'in', filtered_ids['zip'])],
            'l10n_mx_edi_locality_id': [('id', 'in', filtered_ids['locality'])],
            'state_id': [('id', 'in', filtered_ids['state'])],
            'l10n_mx_edi_municipality_id': [('id', 'in', filtered_ids['municipality'])]
        }

        result = dict(domain=domain)

        colony_count = self.env['res.country.colony'].sudo().search_count(domain['l10n_mx_edi_colony_id'])
        if colony_count == 1:
            colony = self.env['res.country.colony'].sudo().search(domain['l10n_mx_edi_colony_id'])
            self.l10n_mx_edi_colony_id = colony.id

        return result

    @api.onchange('zip')
    def _onchange_l10n_mx_zip(self):

        result = {}

        if self.zip:
            search_domain = [('code', '=', self.zip)]

            if self.state_id.id:
                search_domain.append(('country_state_id', '=', self.state_id.id))

            items = self.env['l10n.mx.edi.country.state.zipcode'].sudo().search(search_domain)

            filtered_ids = dict(l10n_mx_edi_locality_id=[], l10n_mx_edi_municipality_id=[])

            for row in items:
                if row.municipality_id.id:
                    filtered_ids['l10n_mx_edi_municipality_id'].append(row.municipality_id.id)

                if row.locality_id.id:
                    filtered_ids['l10n_mx_edi_locality_id'].append(row.locality_id.id)

            domain = {
                'l10n_mx_edi_colony_id': [('zip', '=', self.zip)],
                'l10n_mx_edi_locality_id': [('id', 'in', filtered_ids['l10n_mx_edi_locality_id'])],
                'l10n_mx_edi_municipality_id': [('id', 'in', filtered_ids['l10n_mx_edi_municipality_id'])]
            }

            if len(filtered_ids['l10n_mx_edi_municipality_id']) == 1:
                self.l10n_mx_edi_municipality_id = filtered_ids['l10n_mx_edi_municipality_id'][0]

                if not self.state_id.id:
                    self.state_id = self.l10n_mx_edi_municipality_id.country_state_id.id

            elif self.l10n_mx_edi_municipality_id.id and self.l10n_mx_edi_municipality_id.id not in filtered_ids[
                'l10n_mx_edi_municipality_id']:
                self.l10n_mx_edi_municipality_id = False

            if len(filtered_ids['l10n_mx_edi_locality_id']) == 1:
                self.l10n_mx_edi_locality_id = filtered_ids['l10n_mx_edi_locality_id'][0]
            elif self.l10n_mx_edi_locality_id.id and self.l10n_mx_edi_locality_id.id not in filtered_ids[
                'l10n_mx_edi_locality_id']:
                self.l10n_mx_edi_locality_id = False

            colony_count = self.env['res.country.colony'].sudo().search_count(domain['l10n_mx_edi_colony_id'])

            if colony_count == 1:
                colony = self.env['res.country.colony'].sudo().search(domain['l10n_mx_edi_colony_id'])
                self.l10n_mx_edi_colony_id = colony.id

            result['domain'] = domain

        else:
            result['domain'] = {
                'l10n_mx_edi_colony_id': [('country_id', '=', self.country_id.id)],
                'l10n_mx_edi_locality_id': [('country_state_id', '=', self.state_id.id)],
                'l10n_mx_edi_municipality_id': [('country_state_id', '=', self.state_id.id)]
            }

        return result

    @api.one
    @api.depends('country_id')
    def _compute_show_extra_location_fields(self):
        self.l10n_mx_edi_extra_location_fields = self.country_id == self.env.ref('base.mx')

    @api.model
    def _load_xsd_attachments(self):
        res = super(ResCompany, self)._load_xsd_attachments()
        url = 'http://www.sat.gob.mx/sitio_internet/cfd/ComercioExterior11/ComercioExterior11.xsd'  # noqa
        xsd = self.env.ref(
            'l10n_mx_edi.xsd_cached_ComercioExterior11_xsd', False)
        if xsd:
            xsd.unlink()
        _load_xsd_complement(self._cr, None, url)
        return res