from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    parent_l10n_mx_edi_addenda = fields.Many2one(related="parent_id.l10n_mx_edi_addenda")
    addenda_planta = fields.Char(string="Planta", copy=False)
