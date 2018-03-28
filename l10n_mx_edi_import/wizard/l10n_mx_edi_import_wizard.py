# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api, tools, _
import xlrd
from odoo.exceptions import ValidationError, UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, datetime, DEFAULT_SERVER_DATETIME_FORMAT, etree
from xlrd import XLRDError
import logging
from lxml.objectify import fromstring

EDI_NAMESPACES = {
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'cfdi': 'http://www.sat.gob.mx/cfd/3',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
}


class EdiImportLine(models.TransientModel):
    _name = 'l10n.mx.edi.import.wizard.line'

    import_id = fields.Many2one('l10n.mx.edi.import.wizard', required=True)
    uom_code = fields.Char('Unit of Measure')
    product_code = fields.Char('Product Code')
    l10n_mx_edi_code_sat = fields.Char('SAT Code')
    has_product = fields.Boolean()
    product_id = fields.Many2one('product.product', 'Product', compute='_compute_product', store=True)
    product_description = fields.Char('Description')
    product_unit_price = fields.Float('Unit Price', digits=(19, 2))
    price = fields.Float('Price', digits=(19, 2))
    amount = fields.Integer('Amount')

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

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True)

    line_ids = fields.One2many('l10n.mx.edi.import.wizard.line', 'import_id', 'Lines')

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

    @api.multi
    def action_import(self):
        # create invoice here

        if self.validate_import():
            inv_obj = self.env['account.invoice']
            ir_property_obj = self.env['ir.property']

            invoice_lines = []
            for line in self.line_ids:
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

                invoice_lines.append((0, 0, {
                    'name': line.product_description,
                    'price_unit': line.product_unit_price,
                    'quantity': line.amount,
                    'product_id': line.product_id.id,
                    'uom_id': line.product_id.uom_id.id,
                    'account_id': account_id,
                    'invoice_line_tax_ids': [(6, 0, [tax.id for tax in line.invoice_line_tax_ids])],
                }))

            invoice = inv_obj.create({
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
                'currency_id': self.currency_id.id,
                'payment_term_id': self.payment_term_id.id,
                'fiscal_position_id': self.fiscal_position_id.id if self.fiscal_position_id else self.partner_id.property_account_position_id.id,
                'user_id': self.env.user.id,
                'comment': '',
            })

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

        concepts_section = getattr(xml, 'Conceptos', False)

        if concepts_section:
            lines = []
            for i in range(concepts_section.countchildren()):
                item = concepts_section.Concepto[i]
                AccountTax = self.env['account.tax']
                tax_ids = []

                if self.version == '3.3':
                    for tIndex in range(item.Impuestos.Traslados.countchildren()):

                        concept_tax_section = getattr(item, 'Impuestos')

                        if concept_tax_section:
                            tax = concept_tax_section.Traslados.Traslado[0]
                            tasa = float(tax.attrib['TasaOCuota']) * 100

                            tax_item = AccountTax.search([('amount', '=', tasa), ('type_tax_use', '=', 'sale')], limit=1)

                            if tax_item.id:
                                tax_ids.append(tax_item.id)

                line = {
                    'import_id': self.id,
                    'uom_code': item.attrib.get('ClaveUnidad', item.attrib.get('Unidad')),
                    'l10n_mx_edi_code_sat': item.attrib.get('ClaveProdServ'),
                    'product_code': item.attrib.get('NoIdentificacion'),
                    'amount': float(item.attrib.get('Cantidad', item.attrib.get('cantidad', 0))),
                    'price': float(item.attrib.get('Importe', item.attrib.get('importe', 0))),
                    'product_unit_price': float(item.attrib.get('ValorUnitario', item.attrib.get('valorUnitario', 0))),
                    'product_description': item.attrib.get('Descripcion', item.attrib.get('descripcion', False)),
                    'invoice_line_tax_ids': [(6, 0, tax_ids)],
                }

                lines.append((0, 0, line))

            self.line_ids = lines

        return True
