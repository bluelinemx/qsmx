# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    l10n_mx_cfdi_uuid = fields.Char('UUID')

    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self, vals):
        if vals.get('l10n_mx_cfdi_uuid') and len(vals.get('l10n_mx_cfdi_uuid')) >0 :
            search = self.sudo().search([('l10n_mx_cfdi_uuid', '=', vals.get('l10n_mx_cfdi_uuid'))])

            if len(search):
                raise ValidationError(_('The Fiscal Folio %s is already used in the system.') % vals.get('l10n_mx_cfdi_uuid'))

        return super(AccountInvoice, self).create(vals)


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    filter_product_code = fields.Char()
    filter_product_name = fields.Char()

    @api.onchange('filter_product_code')
    def _onchange_filter_product_code(self):

        result = {}

        if self.filter_product_code:
            search_domain = [('default_code', '=', self.filter_product_code)]
            domain = {
                'product_id': search_domain,
            }
            result['domain'] = domain

        return result