# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict', domain="[('country_id', '=', country_id)]", change_default=True)
    l10n_mx_edi_international_trade = fields.Boolean('International Trade')
    l10n_mx_edi_curp = fields.Char(string='CURP')

    l10n_mx_edi_locality_id = fields.Many2one('res.country.state.locality', string='Location', domain="[('country_state_id', '=', state_id)]", change_default=True)
    l10n_mx_edi_colony_id = fields.Many2one('res.country.colony', string='Colony', domain="[('country_id', '=', country_id)]", change_default=True)
    l10n_mx_edi_municipality_id = fields.Many2one('res.country.state.municipality', string='Municipality', domain="[('country_state_id', '=', state_id)]", change_default=True)
    l10n_mx_edi_extra_location_fields = fields.Boolean(compute='_compute_show_extra_location_fields')

    @api.onchange('l10n_mx_edi_locality_id')
    def onchange_l10n_mx_edi_locality_id(self):
        self.l10n_mx_edi_locality = self.l10n_mx_edi_locality_id.name if self.l10n_mx_edi_locality_id.id else None

    @api.onchange('l10n_mx_edi_colony_id')
    def onchange_l10n_mx_edi_locality_id(self):
        self.l10n_mx_edi_colony = self.l10n_mx_edi_colony_id.name if self.l10n_mx_edi_colony_id.id else None

        if self.l10n_mx_edi_colony_id.id:
            self.zip = self.l10n_mx_edi_colony_id.zip

    @api.one
    @api.depends('country_id')
    def _compute_show_extra_location_fields(self):
        self.l10n_mx_edi_extra_location_fields = self.country_id == self.env.ref('base.mx')