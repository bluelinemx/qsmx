# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from functools import partial


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    client_identification_number = fields.Char('No. Identification')


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def get_l10n_mx_edi_usage_label(self):
        Invoice = self.with_context({'lang': self.partner_id.lang})

        return Invoice.env['ir.translation']._get_source(None, ('selection', ), self.partner_id.lang,
                                                         dict(self._fields['l10n_mx_edi_usage']._description_selection(self.env)).get(self.l10n_mx_edi_usage)
                                                         )

    @api.multi
    def _get_tax_amount_by_group(self):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        fmt = partial(formatLang, self.with_context(lang=self.partner_id.lang).env, currency_obj=currency)
        res = {}
        for line in self.tax_line_ids:
            res.setdefault(line.tax_id.tax_group_id, {'base': 0.0, 'amount': 0.0})
            res[line.tax_id.tax_group_id]['amount'] += line.amount
            res[line.tax_id.tax_group_id]['base'] += line.base
        res = sorted(res.items(), key=lambda l: l[0].sequence)
        res = [(
            r[0].name, r[1]['amount'], r[1]['base'],
            fmt(r[1]['amount']), fmt(r[1]['base']),
        ) for r in res]
        return res
