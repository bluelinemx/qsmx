# -*- coding: utf-8 -*-

from odoo import models, fields


class Partner(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    rfc = fields.Char(string='RFC', size=13)
