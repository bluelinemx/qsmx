# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.addons.l10n_mx_edi.models.account_invoice import CFDI_XSLT_CADENA
from odoo.exceptions import ValidationError, UserError
from lxml import etree
from lxml.builder import E

from odoo.addons.l10n_mx_edi.models.account_invoice import create_list_html


class Invoice(models.Model):
    _inherit = 'account.invoice'

    l10n_mx_edi_incoterm_id = fields.Many2one('l10n.mx.edi.external.incoterms', string='Incoterm',
                                  help="International Commercial Terms are a series of predefined commercial terms "
                                       "used in international transactions.", readonly=True,
                                  states={'draft': [('readonly', False)]})

    l10n_mx_edi_international_trade = fields.Boolean('International Trade', change_default=True)

    l10n_mx_edi_is_origin_certificate = fields.Boolean('Is Origin Certificate', readonly=True,
                                                       states={'draft': [('readonly', False)]})
    l10n_mx_edi_origin_certificate_number = fields.Char('No. Origin Certificate', readonly=True,
                                                        states={'draft': [('readonly', False)]})

    l10n_mx_edi_customs_amount_total_usd = fields.Monetary(string="Amount USD", compute='_compute_customs_amount_total_usd')

    @api.onchange('partner_id')
    def _onchange_partner_id_international_trade(self):
        self.l10n_mx_edi_international_trade = self.partner_id.l10n_mx_edi_international_trade

    @api.one
    @api.depends('invoice_line_ids.l10n_mx_edi_customs_price_usd')
    def _compute_customs_amount_total_usd(self):
        self.l10n_mx_edi_customs_amount_total_usd = sum([l.l10n_mx_edi_customs_price_usd for l in self.invoice_line_ids])

    # @api.onchange('partner_id')
    # def _onchange_international_trade(self):
    #     self.l10n_mx_edi_international_trade = self.partner_id.l10n_mx_edi_international_trade
    #     for line in self.invoice_line_ids:
    #         line.l10n_mx_edi_international_trade = self.l10n_mx_edi_international_trade
    #
    # @api.one
    # @api.depends('partner_id', 'partner_id.l10n_mx_edi_international_trade')
    # def _compute_international_trade(self):
    #     self.l10n_mx_edi_international_trade = self.partner_id.l10n_mx_edi_international_trade
    #     for line in self.invoice_line_ids:
    #         line.l10n_mx_edi_international_trade = self.l10n_mx_edi_international_trade

    @api.multi
    @api.constrains('l10n_mx_edi_origin_certificate_number')
    def _check_origin_certificate_number(self):
        for record in self:
            if record.l10n_mx_edi_is_origin_certificate and not (
                    6 < len(record.l10n_mx_edi_origin_certificate_number) < 40):
                raise ValidationError(_('The origin certificate number must be between 6 and 40 characters in length.'))

    # @api.multi
    # def _l10n_mx_edi_create_cfdi(self):
    #     if not self.l10n_mx_edi_international_trade:
    #         return super(Invoice, self)._l10n_mx_edi_create_cfdi()
    #
    #     bad_line = self.invoice_line_ids.filtered(
    #         lambda l: not (l.product_id.l10n_mx_customs_tax_fraction_id.customs_uom_id.id if l.product_id.l10n_mx_customs_tax_fraction_id else False) or not l.product_id.l10n_mx_customs_tax_fraction_id.id or
    #                   not l.l10n_mx_edi_customs_quantity)
    #     if bad_line:
    #         line_name = bad_line.mapped('product_id.name')
    #         return {'error': _(
    #             'Please verify that Qty UMT has a value in the line, '
    #             'and that the product has set a value in Tariff Fraction and '
    #             'in UMT Aduana.<br/><br/>This for the products:'
    #         ) + create_list_html(line_name)}
    #
    #     return super(Invoice, self)._l10n_mx_edi_create_cfdi()

    @api.multi
    def _l10n_mx_edi_create_cfdi_values(self):
        '''Create the values to fill the CFDI template.
        '''
        self.ensure_one()

        values = super(Invoice, self)._l10n_mx_edi_create_cfdi_values()

        if not self.l10n_mx_edi_international_trade:
            return values

        precision_digits = self.env['decimal.precision'].precision_get('Account')

        ctx = dict(company_id=self.company_id.id, date=self.date_invoice)
        mxn = self.env.ref('base.MXN').with_context(ctx)
        usd = self.env.ref('base.USD').with_context(ctx)
        invoice_currency = self.currency_id.with_context(ctx)

        values.update({
            'usd': usd,
            'mxn': mxn,

            'receiver_reg_trib': values.get('customer').vat,
            'usd_rate': '%0.*f' % (precision_digits, usd.compute(1, mxn)),
            'incoterm_code': self.l10n_mx_edi_incoterm_id.code if self.l10n_mx_edi_incoterm_id.id else False,
            'is_origin_certificate': 1 if self.l10n_mx_edi_is_origin_certificate else 0,
            'origin_certificate_number': self.l10n_mx_edi_origin_certificate_number if self.l10n_mx_edi_is_origin_certificate else False,
            'amount_total_usd': '%0.*f' % (precision_digits, self.amount_total),
            'europe_group': self.env.ref('base.europe'),
        })

        values['quantity_aduana'] = lambda p, i: sum([
            l.l10n_mx_edi_customs_quantity for l in i.invoice_line_ids
            if l.product_id == p])
        values['unit_value_usd'] = lambda l, c, u: c.compute(
            l.l10n_mx_edi_customs_price_unit, u)
        values['amount_usd'] = lambda origin, dest, amount: origin.compute(
            amount, dest)
        values['total_usd'] = lambda i, u, c: sum([
            round(l.l10n_mx_edi_customs_quantity * c.compute(
                l.l10n_mx_edi_customs_price_unit, u), 2) for l in i])

        return values


class InvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    l10n_mx_edi_international_trade = fields.Boolean('International Trade', related='invoice_id.l10n_mx_edi_international_trade')
    l10n_mx_edi_tax_fraction_id = fields.Many2one(
        'l10n.mx.edi.external.customs.tax.fraction', 'Tariff Fraction', store=True,
        related='product_id.l10n_mx_customs_tax_fraction_id',
        help='It is used to express the key of the tariff fraction '
             'corresponding to the description of the product to export. Node '
             '"FraccionArancelaria" to the concept.')

    l10n_mx_edi_customs_quantity = fields.Float(string='Customs Quantity', digits=dp.get_precision('Product Unit of Measure'), compute='_compute_customs_fields', store=True)
    l10n_mx_edi_customs_price_unit = fields.Float(string='Customs Unit Price', digits=dp.get_precision('Product Price'), compute='_compute_customs_fields', store=True)
    l10n_mx_edi_customs_price_usd = fields.Float(string='Customs Price USD', digits=dp.get_precision('Product Price'), compute='_compute_customs_price_usd', store=True)

    @api.one
    @api.depends('l10n_mx_edi_international_trade', 'product_id', 'price_unit', 'quantity', 'uom_id')
    def _compute_customs_fields(self):

        if self.product_id.l10n_mx_customs_tax_fraction_id.customs_uom_id and self.l10n_mx_edi_international_trade:
            product_uom_factor = self.uom_id._compute_quantity(self.quantity, self.product_id.l10n_mx_customs_tax_fraction_id.customs_uom_id.uom_id)

            self.l10n_mx_edi_customs_quantity = product_uom_factor

            ctx = dict(company_id=self.invoice_id.company_id.id, date=self.invoice_id.date_invoice)
            usd = self.env.ref('base.USD').with_context(ctx)
            invoice_currency = self.invoice_id.currency_id.with_context(ctx)

            price_unit = self.uom_id._compute_price(self.price_unit, self.product_id.l10n_mx_customs_tax_fraction_id.customs_uom_id.uom_id)

            # if self.product_id.l10n_mx_customs_tax_fraction_id:
            self.l10n_mx_edi_customs_price_unit = invoice_currency.compute(price_unit, usd)
        else:
            self.l10n_mx_edi_customs_quantity = 0
            self.l10n_mx_edi_customs_price_unit = 0

    @api.one
    @api.depends('l10n_mx_edi_international_trade', 'product_id', 'price_unit', 'quantity', 'uom_id')
    def _compute_customs_price_usd(self):
        if self.l10n_mx_edi_international_trade:
            ctx = dict(company_id=self.invoice_id.company_id.id, date=self.invoice_id.date_invoice)
            usd = self.env.ref('base.USD').with_context(ctx)
            invoice_currency = self.invoice_id.currency_id.with_context(ctx)

            self.l10n_mx_edi_customs_price_usd = invoice_currency.compute(self.price_subtotal, usd)

        else:
            self.l10n_mx_edi_customs_price_usd = 0