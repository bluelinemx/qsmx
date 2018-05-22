# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api, tools, _
import xlrd
from odoo.exceptions import ValidationError, UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, datetime, DEFAULT_SERVER_DATETIME_FORMAT, etree
from xlrd import XLRDError
import logging
from lxml.objectify import fromstring
from odoo.addons import decimal_precision as dp

EDI_NAMESPACES = {
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'cfdi': 'http://www.sat.gob.mx/cfd/3',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
}


class EdiImportTax(models.TransientModel):
    _name = 'l10n.mx.edi.import.wizard.tax'

    import_id = fields.Many2one('l10n.mx.edi.import.wizard', required=True)

    name = fields.Char('Name')
    amount = fields.Float('Amount', digits=(12, 6))
    amount_rounding = fields.Float('Amount Rounding', digits=(12, 6))
    base = fields.Float('Amount Rounding', digits=(12, 6))
    manual = fields.Boolean('Manual')

    tax_id = fields.Many2one('account.tax', 'Tax')
    account_id = fields.Many2one('account.account', 'Account')
    company_id = fields.Many2one('res.company', 'Company')
    currency_id = fields.Many2one('res.currency', 'Currency')


class EdiImportLine(models.TransientModel):
    _name = 'l10n.mx.edi.import.wizard.line'

    import_id = fields.Many2one('l10n.mx.edi.import.wizard', required=True)
    uom_code = fields.Char('Unit of Measure')
    product_code = fields.Char('Product Code')
    l10n_mx_edi_code_sat = fields.Char('SAT Code')
    has_product = fields.Boolean()

    product_id = fields.Many2one('product.product', 'Product', compute='_compute_product', store=True)
    product_description = fields.Char('Description')

    currency_id = fields.Many2one('res.currency', 'Currency')

    price_unit = fields.Float('Unit Price', digits=(12, 6))
    price_subtotal = fields.Float('Price', digits=(12, 6))
    price_total = fields.Float('Price', digits=(12, 6))
    total_taxes = fields.Float('Total Taxes', digits=(12, 6))
    quantity = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), default=1)
    discount = fields.Float('Discount', digits=(12, 6))

    invoice_line_tax_ids = fields.Many2many('account.tax',
                                            'l10n_mx_edi_import_wizard_line_tax_rel', 'invoice_line_id', 'tax_id',
                                            string='Taxes')

    def product_lookup(self):
        if self.product_code:
            product = self.env['product.product'].search([('default_code', '=', self.product_code)])

            return product

        return False

    @api.model
    def create(self, values):
        item = super().create(values)
        item._compute_product()
        return item

    @api.one
    def _compute_product(self):
        product = self.product_lookup()

        self.has_product = product and product.id is not False

        if self.has_product:
            self.product_id = product.id


def get_xml_value(xml, selector, key):
    if selector:
        el = xml.find(selector, EDI_NAMESPACES)
        if el:
            return el.get(key.lower(), el.get(key.capitalize()))
    else:
        xml.get(key.lower(), xml.get(key.capitalize()))


class EdiImport(models.TransientModel):
    _name = 'l10n.mx.edi.import.wizard'

    xml_file = fields.Binary(required=True)
    xml_content = fields.Text(readonly=True)
    name = fields.Char('Folio')

    version = fields.Char()

    l10n_mx_edi_usage = fields.Selection([
        ('G01', 'Acquisition of merchandise'),
        ('G02', 'Returns, discounts or bonuses'),
        ('G03', 'General expenses'),
        ('I01', 'Constructions'),
        ('I02', 'Office furniture and equipment investment'),
        ('I03', 'Transportation equipment'),
        ('I04', 'Computer equipment and accessories'),
        ('I05', 'Dices, dies, molds, matrices and tooling'),
        ('I06', 'Telephone communications'),
        ('I07', 'Satellite communications'),
        ('I08', 'Other machinery and equipment'),
        ('D01', 'Medical, dental and hospital expenses.'),
        ('D02', 'Medical expenses for disability'),
        ('D03', 'Funeral expenses'),
        ('D04', 'Donations'),
        ('D05', 'Real interest effectively paid for mortgage loans (room house)'),
        ('D06', 'Voluntary contributions to SAR'),
        ('D07', 'Medical insurance premiums'),
        ('D08', 'Mandatory School Transportation Expenses'),
        ('D09', 'Deposits in savings accounts, premiums based on pension plans.'),
        ('D10', 'Payments for educational services (Colegiatura)'),
        ('P01', 'To define'),
    ], 'Usage', default='P01',
        help='Used in CFDI 3.3 to express the key to the usage that will '
             'gives the receiver to this invoice. This value is defined by the '
             'customer. \nNote: It is not cause for cancellation if the key set is '
             'not the usage that will give the receiver of the document.')

    l10n_mx_edi_pac_status = fields.Char(default='to_sign')
    l10n_mx_edi_sat_status = fields.Char(default='none')
    l10n_mx_edi_cfdi_name = fields.Char()
    l10n_mx_edi_cfdi_uuid = fields.Char('UUID')
    l10n_mx_edi_cfdi = fields.Char("CFDI")
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char('RFC')
    l10n_mx_edi_cfdi_supplier_name = fields.Char('Name')
    l10n_mx_edi_cfdi_customer_rfc = fields.Char('RFC')
    l10n_mx_edi_cfdi_customer_name = fields.Char('Name')
    l10n_mx_edi_cfdi_amount = fields.Float('Amount', digits=(10, 2))
    currency_code = fields.Char('Currency Code')
    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_edi_values', store=True)
    exchange_rate = fields.Float(string='Current Rate', digits=(12, 6))
    company_id = fields.Many2one('res.partner', 'Company', compute='_compute_edi_values', store=True)
    partner_id = fields.Many2one('res.partner', 'Client', compute='_compute_edi_values', store=True)
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', compute='_compute_edi_values', store=True)
    state = fields.Char("State")
    date_invoice = fields.Datetime()
    payment_term_name = fields.Char("Payement Term", size=255)
    has_payment_term = fields.Boolean()
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Term', compute='_compute_edi_values', store=True)
    l10n_mx_edi_cfdi_certificate_id = fields.Char()
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    fiscal_position_code = fields.Char('Fiscal Position Code')
    fiscal_position_id = fields.Many2one('account.fiscal.position', 'Fiscal Position', compute='_compute_edi_values', store=True)

    amount_untaxed = fields.Float(string='Untaxed Amount', store=True, readonly=True, digits=(12, 6))
    amount_tax = fields.Float(string='Taxes', store=True, readonly=True, digits=(12, 6))
    amount_total = fields.Float(string='Total', store=True, readonly=True, digits=(12, 6))

    line_ids = fields.One2many('l10n.mx.edi.import.wizard.line', 'import_id', 'Lines')
    tax_line_ids = fields.One2many('l10n.mx.edi.import.wizard.tax', 'import_id', 'Tax Lines')

    @api.multi
    @api.depends('currency_code', 'payment_term_name', 'fiscal_position_code', 'l10n_mx_edi_cfdi_supplier_rfc', 'l10n_mx_edi_cfdi_customer_rfc')
    def _compute_edi_values(self):
        self.ensure_one()
        if self.fiscal_position_code:
            fiscal_position = self.env['account.fiscal.position'].search(
                [('l10n_mx_edi_code', '=', self.fiscal_position_code)], limit=1)
            self.fiscal_position_id = fiscal_position.id or False

        if self.payment_term_name:
            payment_term = self.env['account.payment.term'].search(
                [('name', '=', self.payment_term_name)], limit=1)
            self.payment_term_id = payment_term.id or False
            self.has_payment_term = payment_term.id is not False

        if self.currency_code:
            self.currency_id = self.env['res.currency'].search([('name', '=', self.currency_code)]).id
        else:
            self.currency_id = False

        if self.l10n_mx_edi_cfdi_supplier_rfc:
            supplier = self.env['res.partner'].search([('vat', '=', self.l10n_mx_edi_cfdi_supplier_rfc)], limit=1)

            self.company_id = supplier.id or False
        else:
            self.company_id = False

        if self.l10n_mx_edi_cfdi_customer_rfc:
            supplier = self.env['res.partner'].search([('vat', '=', self.l10n_mx_edi_cfdi_customer_rfc)], limit=1)

            self.partner_id = supplier.id or False

            if self.partner_id:
                addr = self.partner_id.address_get(['delivery'])
                self.partner_shipping_id = addr and addr.get('delivery')
        else:
            self.partner_id = False

    @api.multi
    def action_validate(self):

        if self.process_xml_file():
            preview_form = self.env.ref('l10n_mx_edi_import.l10n_mx_edi_import_wizard_preview_form')

            return {
                'name': _('Preview Data'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': self.id,
                'res_model': self._name,
                'views': [(preview_form.id, 'form')],
                'view_id': preview_form.id,
                'target': 'new',
            }

    @api.multi
    def action_upload(self):
        upload_form = self.env.ref('l10n_mx_edi_import.l10n_mx_edi_import_wizard_form')

        return {
            'name': _('Preview Data'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'views': [(upload_form.id, 'form')],
            'view_id': upload_form.id,
            'target': 'new',
        }

    def validate_import(self):
        invalid = filter(lambda p: not p.product_id, self.line_ids)

        if len(list(invalid)):
            raise UserError(
                _('Some invoice lines doesnt have a valid product. Please update or upload another XML file.'))

        return True

    def get_invoice_tax_line_values_from_tax_line(self, line):

        return {
            'name': line.name,
            'tax_id': line.tax_id.id,
            'account_id': line.account_id.id,
            'company_id': line.company_id.id,
            'currency_id': line.currency_id.id,
            'amount': line.amount,
            'amount_rounding': line.amount_rounding,
            'base': line.base,
            'manual': line.manual,
        }


    def get_invoice_line_values_from_line(self, line):
        ir_property_obj = self.env['ir.property']

        account_id = False
        if line.product_id.id:
            account_id = line.product_id.property_account_income_id.id
        if not account_id:
            inc_acc = ir_property_obj.get('property_account_income_categ_id', 'product.category')
            account_id = self.fiscal_position_id.map_account(inc_acc).id if inc_acc else False
        if not account_id:
            raise UserError(
                _(
                    'There is no income account defined for this product: "%s". You may have to install a chart of account from Accounting app, settings menu.') %
                (line.product_id.name,))

        return {
            'name': line.product_description,
            'price_unit': line.price_unit,
            'price_subtotal': line.price_subtotal,
            'price_subtotal_signed': line.price_subtotal,
            'price_total': line.price_total,
            'discount': line.discount,
            'quantity': line.quantity,
            'product_id': line.product_id.id,
            'uom_id': line.product_id.uom_id.id,
            'account_id': account_id,
            'invoice_line_tax_ids': [(6, 0, [tax.id for tax in line.invoice_line_tax_ids])],
        }

    def get_invoice_creation_values(self):
        invoice_lines = []

        amount_untaxed = 0
        amount_untaxed_signed = 0
        amount_tax = 0
        amount_total = 0
        amount_total_signed = 0
        amount_total_company_signed = 0

        for line in self.line_ids:
            invoice_lines.append((0, 0, self.get_invoice_line_values_from_line(line)))

            amount_untaxed += line.price_subtotal
            amount_untaxed_signed += line.price_subtotal
            amount_tax += line.total_taxes
            amount_total_signed += line.price_subtotal + line.total_taxes
            amount_total_company_signed += line.price_subtotal + line.total_taxes

        amount_total = amount_untaxed + self.amount_tax

        tax_lines = []
        for line in self.tax_line_ids:
            tax_lines.append((0, 0, self.get_invoice_tax_line_values_from_tax_line(line)))

        return {
            'type': 'out_invoice',
            'state': 'draft',
            'reference': False,
            'move_name': "F-/{name}".format(name=self.name),
            'number': "F-/{name}".format(name=self.name),
            'date_invoice': self.date_invoice,
            'partner_shipping_id': self.partner_shipping_id.id,
            'l10n_mx_edi_usage': self.l10n_mx_edi_usage,
            'l10n_mx_edi_pac_status': self.l10n_mx_edi_pac_status,
            'l10n_mx_edi_sat_status': self.l10n_mx_edi_sat_status,
            'l10n_mx_edi_cfdi_supplier_rfc': self.l10n_mx_edi_cfdi_supplier_rfc,
            'l10n_mx_edi_cfdi_customer_rfc': self.l10n_mx_edi_cfdi_customer_rfc,
            'account_id': self.partner_id.property_account_receivable_id.id,
            'partner_id': self.partner_id.id,
            'invoice_line_ids': invoice_lines,
            'tax_line_ids': tax_lines,
            'currency_id': self.currency_id.id,
            'payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id if self.fiscal_position_id else self.partner_id.property_account_position_id.id,
            'user_id': self.env.user.id,
            'comment': '',

            'amount_untaxed': amount_untaxed,
            'amount_untaxed_signed': amount_untaxed_signed,
            'amount_tax': self.amount_tax or amount_tax,
            'amount_total': amount_total,
            'amount_total_signed': amount_total_signed,
            'amount_total_company_signed': amount_total_company_signed,
        }

    def create_invoice(self):
        inv_obj = self.env['account.invoice']
        invoice = inv_obj.create(self.get_invoice_creation_values())

        filename = ('%s-%s-MX-Invoice-%s.xml' % (
            invoice.journal_id.code, invoice.number, self.version.replace('.', '-'))).replace('/', '')
        ctx = self.env.context.copy()
        ctx.pop('default_type', False)
        invoice.l10n_mx_edi_cfdi_name = filename

        attachment_id = self.env['ir.attachment'].with_context(ctx).create({
            'name': filename,
            'res_id': invoice.id,
            'res_model': invoice._name,
            'datas': self.xml_file,
            'datas_fname': filename,
            'description': 'Mexican invoice',
        })

        self.invoice_id = invoice.id

        invoice.action_invoice_open()

        return invoice

    @api.multi
    def action_import(self):
        # create invoice here

        if self.validate_import():

            self.create_invoice()

            return self.do_finish_action()

    def do_finish_action(self):
        if self.invoice_id.id or True:
            action = self.env.ref('account.action_invoice_tree1').read()[0]

            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = self.invoice_id.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def process_xml_file(self):
        try:
            xml = fromstring(base64.b64decode(self.xml_file))
            self.xml_content = etree.tostring(xml, pretty_print=True)
        except:
            raise ValidationError('Unable to parse XML file')

        self.version = xml.attrib.get('Version')
        self.name = xml.attrib.get('Folio')
        self.date_invoice = datetime.strptime(xml.attrib.get('Fecha'), '%Y-%m-%dT%H:%M:%S') if xml.attrib.get('Fecha') else False
        self.currency_code = xml.attrib.get('Moneda')
        self.exchange_rate = xml.attrib.get('TipoCambio', 1)
        self.l10n_mx_edi_cfdi_amount = float(xml.attrib.get('Total', xml.attrib.get('total', 0)))

        self.amount_untaxed = float(xml.attrib.get('SubTotal', xml.attrib.get('subTotal', 0)))
        self.amount_total = float(xml.attrib.get('Total', xml.attrib.get('total', 0)))

        taxes_section = getattr(xml, 'Impuestos', False)
        if taxes_section:
            self.amount_tax = float(taxes_section.attrib.get('TotalImpuestosTrasladados', 0))

        self.payment_term_name = xml.attrib.get('CondicionesDePago') or ''

        self.l10n_mx_edi_cfdi_supplier_name = xml.Emisor.attrib.get('Nombre', xml.Emisor.attrib.get('nombre'))
        self.l10n_mx_edi_cfdi_supplier_rfc = xml.Emisor.attrib.get('Rfc', xml.Emisor.attrib.get('rfc'))
        self.l10n_mx_edi_cfdi_customer_name = xml.Receptor.attrib.get('Nombre', xml.Receptor.attrib.get('nombre'))
        self.l10n_mx_edi_cfdi_customer_rfc = xml.Receptor.attrib.get('Rfc', xml.Receptor.attrib.get('rfc'))
        self.l10n_mx_edi_usage = xml.Receptor.attrib.get('UsoCFDI')

        if not self.company_id:
            raise UserError(
                _('Unable to find company %s with RFC %s') % (
                    self.l10n_mx_edi_cfdi_supplier_name, self.l10n_mx_edi_cfdi_supplier_rfc))

        if self.company_id and self.company_id.id != self.env.user.partner_id.company_id.id:
            raise UserError(
                _('Unable to process XML from company other than %s with RFC %s') % (
                self.env.user.partner_id.company_id.name, self.env.user.partner_id.company_id.vat))

        if not self.partner_id:
            raise UserError(
                _('Unable to find client %s with RFC %s') % (
                    self.l10n_mx_edi_cfdi_customer_name, self.l10n_mx_edi_cfdi_customer_rfc))

        complemento_section = getattr(xml, 'Complemento', False)

        timbre = complemento_section.find('tfd:TimbreFiscalDigital', EDI_NAMESPACES) if complemento_section else False

        if timbre is not None:
            self.l10n_mx_edi_cfdi_uuid = timbre.get('UUID')

            if self.l10n_mx_edi_cfdi_uuid:
                self.l10n_mx_edi_pac_status = 'signed'
                self.l10n_mx_edi_sat_status = 'valid'

        AccountTax = self.env['account.tax']

        concepts_section = getattr(xml, 'Conceptos', False)

        if concepts_section:
            lines = []
            for i in range(concepts_section.countchildren()):
                item = concepts_section.Concepto[i]
                tax_ids = []
                total_taxes = 0

                if self.version == '3.3':
                    for tIndex in range(item.Impuestos.Traslados.countchildren()):

                        concept_tax_section = getattr(item, 'Impuestos')

                        if concept_tax_section:
                            tax = concept_tax_section.Traslados.Traslado[0]
                            tasa = float(tax.attrib['TasaOCuota']) * 100
                            total_taxes += float(tax.attrib.get('Importe', 0))

                            tax_item = AccountTax.search([('amount', '=', tasa), ('type_tax_use', '=', 'sale')], limit=1)

                            if tax_item.id:
                                tax_ids.append(tax_item.id)

                price_subtotal = float(item.attrib.get('Importe', item.attrib.get('importe', 0)))
                quantity = float(item.attrib.get('Cantidad', item.attrib.get('cantidad', 0)))
                price_unit = float(item.attrib.get('ValorUnitario', item.attrib.get('valorUnitario', 0)))

                line = {
                    'import_id': self.id,
                    'uom_code': item.attrib.get('ClaveUnidad', item.attrib.get('Unidad')),
                    'l10n_mx_edi_code_sat': item.attrib.get('ClaveProdServ'),
                    'product_code': item.attrib.get('NoIdentificacion'),
                    'quantity': quantity,
                    'price_unit': price_unit,
                    'price_subtotal': price_subtotal,
                    'price_total': price_subtotal + total_taxes,
                    'total_taxes': total_taxes,
                    'currency_id': self.currency_id,
                    'discount': 0,
                    'product_description': item.attrib.get('Descripcion', item.attrib.get('descripcion', False)),
                    'invoice_line_tax_ids': [(6, 0, tax_ids)],
                }

                lines.append((0, 0, line))

            self.line_ids = lines

            if taxes_section:
                tax_lines = []
                transfers_section = getattr(taxes_section, 'Traslados', False)
                if transfers_section:

                    for i in range(transfers_section.countchildren()):
                        item = transfers_section.Traslado[i]
                        importe = float(item.attrib.get('Importe', item.attrib.get('importe', 0)))
                        impuesto = item.attrib.get('Impuesto', item.attrib.get('impuesto', False))
                        tasa = float(item.attrib.get('TasaOCuota', item.attrib.get('tasa', 0))) * 100
                        tax_item = AccountTax.search([('amount', '=', tasa), ('type_tax_use', '=', 'sale')], limit=1)

                        if tax_item.id:
                            line = {
                                'name': tax_item.name,
                                'tax_id': tax_item.id,
                                'account_id': tax_item.account_id.id,
                                'currency_id': self.currency_id,
                                'company_id': self.env.user.partner_id.company_id.id,
                                'amount': importe,
                                'base': self.amount_untaxed,
                                'manual': True,
                            }

                            tax_lines.append((0, 0, line))

                    self.tax_line_ids = tax_lines

        return True
