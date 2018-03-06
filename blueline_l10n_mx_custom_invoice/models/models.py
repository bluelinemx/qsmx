# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime

from odoo.tools import DEFAULT_SERVER_TIME_FORMAT


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def get_l10n_mx_edi_usages(self):
        return dict(self._fields['l10n_mx_edi_usage'].selection)