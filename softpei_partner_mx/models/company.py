# -*- coding: utf-8 -*-

from odoo import models, fields


class Partner(models.Model):
    _inherit = 'res.company'

    rfc = fields.Char(string='RFC', size=13)
