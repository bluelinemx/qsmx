# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def l10n_mx_edi_is_required(self):
        result = super().l10n_mx_edi_is_required()

        attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
        return result and not attachment_id

