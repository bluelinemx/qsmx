# -*- coding: utf-8 -*-

from odoo import models, fields


class Partner(models.Model):
    _inherit = 'res.partner'

    rfc = fields.Char(string='RFC', size=13)
    factura_portal = fields.Char(string='Portal de Factura')
    other_factura_portal = fields.Char(string='Otro Portal de Factura')
    colony = fields.Char(string='Colonia')
    property_account_position = fields.Many2one('account.fiscal.position', company_dependent=True,
                                                string="Fiscal Position",
                                                help="The fiscal position will determine taxes and accounts used for"
                                                     " the partner.", oldname="property_account_position")

    # hora_insperccion = fields.Float(string='Hora de la Inspección')
    # hora_extra_insperccion = fields.Float(string='Hora extra de la inspección')
    # hora_lider = fields.Float(string='Hora del lider')
    # hora_extra_lider = fields.Float(string='Hora extra del lider')
    # hora_reparador = fields.Float(string='Hora del reparador')
    # hora_extra_reparador = fields.Float(string='Hora extra del reparador')
    # hora_supervidor = fields.Float(string='Hora del supervisor')
    # hora_extra_supervisor = fields.Float(string='Hora extra del supervisor')
    # hora_liaison = fields.Float(string='Hora del Liaison')
    # hora_extra_liaison = fields.Float(string='Hora Extra del Liaison')
