# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_trusted_exporter_number = fields.Char(string='Trusted Exporter Number')
    l10n_mx_edi_locality_id = fields.Many2one('res.country.state.locality', string='Location')
    l10n_mx_edi_colony_id = fields.Many2one('res.country.colony', string='Colony')
    l10n_mx_edi_municipality_id = fields.Many2one('res.country.state.municipality', string='Municipality')

    l10n_mx_edi_extra_location_fields = fields.Boolean(compute='_compute_show_extra_location_fields')

    @api.onchange('l10n_mx_edi_locality_id')
    def onchange_l10n_mx_edi_locality_id(self):
        self.l10n_mx_edi_locality = self.l10n_mx_edi_locality_id.name if self.l10n_mx_edi_locality_id.id else None

    @api.onchange('l10n_mx_edi_colony_id')
    def onchange_l10n_mx_edi_locality_id(self):
        self.l10n_mx_edi_colony = self.l10n_mx_edi_colony_id.name if self.l10n_mx_edi_colony_id.id else None

    @api.one
    @api.depends('country_id')
    def _compute_show_extra_location_fields(self):
        self.l10n_mx_edi_extra_location_fields = self.country_id == self.env.ref('base.mx')
