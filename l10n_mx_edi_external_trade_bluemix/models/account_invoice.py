# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.addons.l10n_mx_edi.models.account_invoice import CFDI_XSLT_CADENA
from odoo.exceptions import ValidationError
from lxml import etree
from lxml.builder import E


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
    @api.depends('amount_total')
    def _compute_customs_amount_total_usd(self):
        ctx = dict(company_id=self.company_id.id, date=self.date_invoice)
        usd = self.env.ref('base.USD').with_context(ctx)
        invoice_currency = self.currency_id.with_context(ctx)

        self.l10n_mx_edi_customs_amount_total_usd = invoice_currency.compute(self.amount_total, usd)

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
            'receiver_reg_trib': values.get('customer').vat,
            'usd_rate': '%0.*f' % (precision_digits, usd.compute(1, mxn)),
            'incoterm_code': self.l10n_mx_edi_incoterm_id.code if self.l10n_mx_edi_incoterm_id.id else False,
            'is_origin_certificate': 1 if self.l10n_mx_edi_is_origin_certificate else 0,
            'origin_certificate_number': self.l10n_mx_edi_origin_certificate_number if self.l10n_mx_edi_is_origin_certificate else False,
            'amount_total_usd': '%0.*f' % (precision_digits, self.amount_total),
        })

        return values

    @api.multi
    def _l10n_mx_edi_create_cfdi_external_trade_values(self):
        '''Create the values to fill the CFDI External Trade Complement template.
        '''
        self.ensure_one()

        precision_digits = self.env['decimal.precision'].precision_get('Account')
        amount_untaxed = sum(self.invoice_line_ids.mapped(lambda l: l.quantity * l.price_unit))
        amount_discount = sum(self.invoice_line_ids.mapped(lambda l: l.quantity * l.price_unit * l.discount / 100.0))
        partner_id = self.partner_id

        if self.partner_id.type != 'invoice':
            partner_id = self.partner_id.commercial_partner_id

        values = {
            'record': self,
            'incoterm_code': self.l10n_mx_edi_incoterm_id.code if self.l10n_mx_edi_incoterm_id.id else False,
            'is_origin_certificate': 1 if self.l10n_mx_edi_is_origin_certificate else 0,
            'origin_certificate_number': self.l10n_mx_edi_origin_certificate_number if self.l10n_mx_edi_is_origin_certificate else False,
            'currency_name': self.currency_id.name,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'customer': partner_id,
            'amount_total_usd': '%0.*f' % (precision_digits, self.amount_total),
            'amount_total': '%0.*f' % (precision_digits, self.amount_total),
            'amount_untaxed': '%0.*f' % (precision_digits, amount_untaxed),
            'amount_discount': '%0.*f' % (precision_digits, amount_discount) if amount_discount else None,
        }

        values.update(self._l10n_mx_get_serie_and_folio(self.number))
        ctx = dict(company_id=self.company_id.id, date=self.date_invoice)
        mxn = self.env.ref('base.MXN').with_context(ctx)
        usd = self.env.ref('base.USD').with_context(ctx)
        invoice_currency = self.currency_id.with_context(ctx)

        values['rate'] = '%0.*f' % (precision_digits, usd.compute(1, mxn))

        domicile = self.journal_id.l10n_mx_address_issued_id or self.company_id
        values['domicile'] = '%s %s, %s' % (
            domicile.city,
            domicile.state_id.name,
            domicile.country_id.name,
        )

        values['decimal_precision'] = precision_digits
        values['subtotal_wo_discount'] = lambda l: l.quantity * l.price_unit
        values['total_discount'] = lambda l, d: ('%.*f' % (
            int(d), l.quantity * l.price_unit * l.discount / 100)) if l.discount else False

        values['taxes'] = self._l10n_mx_edi_create_taxes_cfdi_values()

        values['tax_name'] = lambda t: {'ISR': '001', 'IVA': '002', 'IEPS': '003'}.get(
            t, False)

        if self.l10n_mx_edi_partner_bank_id:
            digits = [s for s in self.l10n_mx_edi_partner_bank_id.acc_number if s.isdigit()]
            acc_4number = ''.join(digits)[-4:]
            values['account_4num'] = acc_4number if len(acc_4number) == 4 else None
        else:
            values['account_4num'] = None

        return values

    @api.multi
    def _l10n_mx_edi_create_cfdi(self):
        self.ensure_one()

        cfdi = super(Invoice, self)._l10n_mx_edi_create_cfdi()

        version = self.l10n_mx_edi_get_pac_version()

#       only generate external trade complement for cfdi version 3.3 and international trade is enabled in invoice
        if not cfdi.get('cfdi') or version != '3.3' or not self.l10n_mx_edi_international_trade:
            return cfdi

        qweb = self.env['ir.qweb']

        company_id = self.company_id
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()

        tree = etree.fromstring(cfdi.get('cfdi'))

        root = tree.xpath("//*[local-name() = 'Comprobante']")[0]
        complement_node = etree.Element('{http://www.sat.gob.mx/cfd/3}Complemento', nsmap=tree.nsmap)

        values = self._l10n_mx_edi_create_cfdi_external_trade_values()

        content = qweb.render('l10n_mx_edi_external_trade_bluemix.cfdiv33_external_trade', values=values)
        complement = etree.fromstring(content)
        external_complement = complement.xpath("//*[local-name() = 'ComercioExterior']")

        if external_complement:
            complement_node.append(external_complement[0])

        root.append(complement_node)

        tree.attrib['Sello'] = ''
        cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % version, tree)
        tree.attrib['Sello'] = certificate_id.sudo().get_encrypted_cadena(cadena)

        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}


class InvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    l10n_mx_edi_international_trade = fields.Boolean('International Trade', related='invoice_id.l10n_mx_edi_international_trade')

    l10n_mx_edi_customs_quantity = fields.Float(string='Customs Quantity', digits=dp.get_precision('Product Unit of Measure'), compute='_compute_customs_fields', store=True)
    l10n_mx_edi_customs_price_unit = fields.Float(string='Customs Unit Price', digits=dp.get_precision('Product Price'), compute='_compute_customs_fields', store=True)
    l10n_mx_edi_customs_price_usd = fields.Float(string='Customs Price USD', digits=dp.get_precision('Product Price'), compute='_compute_customs_price_usd', store=True)

    @api.one
    @api.depends('l10n_mx_edi_international_trade', 'product_id', 'product_id.l10n_mx_customs_uom_id', 'product_id.l10n_mx_customs_uom_id.uom_id', 'price_unit', 'quantity', 'uom_id')
    def _compute_customs_fields(self):

        if self.product_id.l10n_mx_customs_uom_id and self.l10n_mx_edi_international_trade:
            product_uom_factor = self.uom_id._compute_quantity(self.quantity, self.product_id.l10n_mx_customs_uom_id.uom_id)

            self.l10n_mx_edi_customs_quantity = product_uom_factor

            # if self.product_id.l10n_mx_customs_tax_fraction_id:
            self.l10n_mx_edi_customs_price_unit = self.uom_id._compute_price(self.price_unit, self.product_id.l10n_mx_customs_uom_id.uom_id)
        else:
            self.l10n_mx_edi_customs_quantity = 0
            self.l10n_mx_edi_customs_price_unit = 0

    @api.one
    @api.depends('l10n_mx_edi_international_trade', 'product_id', 'product_id.l10n_mx_customs_uom_id', 'product_id.l10n_mx_customs_uom_id.uom_id', 'price_unit', 'quantity', 'uom_id')
    def _compute_customs_price_usd(self):
        if self.l10n_mx_edi_international_trade:
            ctx = dict(company_id=self.invoice_id.company_id.id, date=self.invoice_id.date_invoice)
            usd = self.env.ref('base.USD').with_context(ctx)
            invoice_currency = self.invoice_id.currency_id.with_context(ctx)

            self.l10n_mx_edi_customs_price_usd = invoice_currency.compute(self.price_total, usd)

        else:
            self.l10n_mx_edi_customs_price_usd = 0