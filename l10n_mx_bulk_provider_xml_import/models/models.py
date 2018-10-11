# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, datetime, DEFAULT_SERVER_DATETIME_FORMAT, etree
from lxml.objectify import fromstring, StringElement, ObjectifiedElement
from odoo.addons import decimal_precision as dp

EDI_NAMESPACES = {
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'cfdi': 'http://www.sat.gob.mx/cfd/3',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
}


class EdiImportTax(models.TransientModel):
    _name = 'l10n.mx.provider.xml.bulk.import.invoice.tax'

    import_id = fields.Many2one('l10n.mx.provider.xml.bulk.import.invoice', required=True, ondelete='CASCADE')

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
    _name = 'l10n.mx.provider.xml.bulk.import.invoice.line'

    import_id = fields.Many2one('l10n.mx.provider.xml.bulk.import.invoice', required=True, ondelete='CASCADE')

    account_analytic_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    uom_code = fields.Char('Unit of Measure')
    product_code = fields.Char('Product Code')
    l10n_mx_edi_code_sat = fields.Char('SAT Code')
    l10n_mx_edi_code_sat_id = fields.Many2one('l10n_mx_edi.product.sat.code', string='SAT Code', compute='_compute_sat_code', ondelete='CASCADE')
    has_product = fields.Boolean()

    product_id = fields.Many2one('product.product', 'Product', compute='_compute_product', store=True, domain="['|', ('l10n_mx_edi_code_sat_id.code', '=', l10n_mx_edi_code_sat), ('default_code', '=', product_code)]")
    product_description = fields.Char('Description')

    currency_id = fields.Many2one('res.currency', 'Currency')

    price_unit = fields.Float('Unit Price', digits=(12, 6))
    price_subtotal = fields.Float('Price', digits=(12, 6))
    price_total = fields.Float('Price', digits=(12, 6))
    total_taxes = fields.Float('Total Taxes', digits=(12, 6))
    quantity = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), default=1)
    discount = fields.Float('Discount', digits=(12, 6))

    invoice_line_tax_ids = fields.Many2many('account.tax',
                                            'l10n_mx_provider_xml_bulk_import_invoice_line_tax_rel', 'invoice_line_id', 'tax_id',
                                            string='Taxes')

    def product_lookup(self):
        product = None

        if self.l10n_mx_edi_code_sat is not False and self.product_code is not False:
            product = self.env['product.product'].search([('l10n_mx_edi_code_sat_id.code', '=', self.l10n_mx_edi_code_sat), ('default_code', '=', self.product_code)])
        # elif self.l10n_mx_edi_code_sat:
        #     product = self.env['product.product'].search(
        #         [('l10n_mx_edi_code_sat_id.code', '=', self.l10n_mx_edi_code_sat)])
        elif self.product_code is not False or len(self.product_code):
            product = self.env['product.product'].search([('default_code', '=', self.product_code)])

        return product if product and product.id else False

    @api.model
    def create(self, values):
        item = super().create(values)
        item._compute_product()
        return item

    @api.one
    @api.depends('l10n_mx_edi_code_sat')
    def _compute_sat_code(self):
        self.l10n_mx_edi_code_sat_id = self.env['l10n_mx_edi.product.sat.code'].sudo().search([('code', '=', self.l10n_mx_edi_code_sat)], limit=1).id

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
    _name = 'l10n.mx.provider.xml.bulk.import.invoice'

    xml_filename = fields.Char(string="Filename")
    xml_file = fields.Binary(required=True)
    xml_content = fields.Text(readonly=True)

    invoice_type = fields.Selection([
        ('in_refund', 'Credit Note'),
        ('in_invoice', 'Vendor Bill'),
    ], string='Invoice Type', default='in_invoice')

    invoice_state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string='Invoice State', default='draft')

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
    refund_invoice_id = fields.Many2one('account.invoice', 'Refunded Invoice', compute='_compute_refunded_invoice', ondelete='CASCADE')
    l10n_mx_edi_redunded_invoice_cfdi_uuid = fields.Char('UUID')
    l10n_mx_edi_cfdi = fields.Char("CFDI")
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char('RFC')
    l10n_mx_edi_cfdi_supplier_name = fields.Char('Name')
    l10n_mx_edi_cfdi_customer_rfc = fields.Char('RFC')
    l10n_mx_edi_cfdi_customer_name = fields.Char('Name')
    l10n_mx_edi_cfdi_amount = fields.Float('Amount', digits=(10, 2))
    currency_code = fields.Char('Currency Code')
    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_edi_values', store=True)
    exchange_rate = fields.Float(string='Current Rate', digits=(12, 6))
    company_id = fields.Many2one('res.company', 'Company', compute='_compute_edi_values', domain="[('partner_id.vat', '=', l10n_mx_edi_cfdi_supplier_rfc)]", store=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', compute='_compute_edi_values', domain="[('vat', '=', l10n_mx_edi_cfdi_customer_rfc)]", store=True)
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', compute='_compute_edi_values',
                                          store=True)
    state = fields.Char("State")
    date_invoice = fields.Datetime()
    payment_term_name = fields.Char("Payement Term", size=255)
    has_payment_term = fields.Boolean()
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Term', compute='_compute_edi_values', store=True)
    l10n_mx_edi_cfdi_certificate_id = fields.Char()
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    fiscal_position_code = fields.Char('Fiscal Position Code')
    fiscal_position_id = fields.Many2one('account.fiscal.position', 'Fiscal Position', compute='_compute_edi_values',
                                         store=True)

    amount_untaxed = fields.Float(string='Untaxed Amount', store=True, readonly=True, digits=(12, 6))
    amount_tax = fields.Float(string='Taxes', store=True, readonly=True, digits=(12, 6))
    amount_total = fields.Float(string='Total', store=True, readonly=True, digits=(12, 6))

    line_ids = fields.One2many('l10n.mx.provider.xml.bulk.import.invoice.line', 'import_id', 'Lines')
    tax_line_ids = fields.One2many('l10n.mx.provider.xml.bulk.import.invoice.tax', 'import_id', 'Tax Lines')

    @api.multi
    @api.depends('currency_code', 'payment_term_name', 'fiscal_position_code', 'l10n_mx_edi_cfdi_supplier_rfc',
                 'l10n_mx_edi_cfdi_customer_rfc')
    def _compute_edi_values(self):
        for item in self:

            if item.fiscal_position_code:
                fiscal_position = self.env['account.fiscal.position'].search(
                    [('l10n_mx_edi_code', '=', item.fiscal_position_code)], limit=1)
                item.fiscal_position_id = fiscal_position.id or False

            if item.payment_term_name:
                payment_term = self.env['account.payment.term'].search(
                    [('name', '=', item.payment_term_name)], limit=1)
                item.payment_term_id = payment_term.id or False
                item.has_payment_term = payment_term.id is not False

            if item.currency_code:
                item.currency_id = self.env['res.currency'].search([('name', '=', item.currency_code)]).id
            else:
                item.currency_id = False

            if item.l10n_mx_edi_cfdi_supplier_rfc:
                supplier = self.env['res.company'].search([('partner_id.vat', '=', item.l10n_mx_edi_cfdi_supplier_rfc)], limit=1)

                item.company_id = supplier.id if supplier.id else False
            else:
                item.company_id = False

            if item.l10n_mx_edi_cfdi_customer_rfc:
                supplier = self.env['res.partner'].search([('vat', '=', item.l10n_mx_edi_cfdi_customer_rfc)], limit=1)

                item.partner_id = supplier.id or False

                if item.partner_id:
                    addr = item.partner_id.address_get(['delivery'])
                    item.partner_shipping_id = addr and addr.get('delivery')
            else:
                item.partner_id = False

    @api.one
    @api.depends('l10n_mx_edi_redunded_invoice_cfdi_uuid')
    def _compute_refunded_invoice(self):
        self.refund_invoice_id = self.env['account.invoice'].sudo().search([('l10n_mx_cfdi_uuid', '=', self.l10n_mx_edi_redunded_invoice_cfdi_uuid)]).id if self.invoice_type == 'in_refund' else False

    @api.multi
    def action_validate(self, refresh=True):
        return self.process_xml_file(refresh=refresh)

    def validate_import(self):
        invalid = filter(lambda p: not p.product_id, self.line_ids)

        # if len(list(invalid)):
        #     raise UserError(
        #         _('Some invoice lines doesnt have a valid product. Please update or upload another XML file.'))

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
            accounts = line.product_id.product_tmpl_id._get_product_accounts()
            account = accounts.get('expense') if line.product_id.type in ['consu', 'service'] else accounts.get('stock_input')
            account_id = account.id
        if not account_id:
            inc_acc = ir_property_obj.get('property_account_expense_categ_id', 'product.category')
            account_id = self.fiscal_position_id.map_account(inc_acc).id if inc_acc else False

        if line.product_id.id and not account_id:
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
            'uom_id': line.product_id.uom_id.id if line.product_id.id else False,
            'account_id': account_id,
            'account_analytic_id': line.account_analytic_id.id,
            'invoice_line_tax_ids': [(6, 0, [tax.id for tax in line.invoice_line_tax_ids])],
            'filter_product_code': line.product_code,
            'filter_product_name': line.product_description,
        }

    def get_invoice_creation_values(self):
        invoice_lines = []

        amount_untaxed = 0
        amount_untaxed_signed = 0
        amount_tax = 0
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
            'type': self.invoice_type,
            'state': self.invoice_state,
            'reference': self.name,
            # 'move_name': "F-/{name}".format(name=self.name),
            # 'number': "F-/{name}".format(name=self.name),
            'date_invoice': self.date_invoice,
            'partner_shipping_id': self.partner_shipping_id.id,
            'l10n_mx_edi_usage': self.l10n_mx_edi_usage,
            'l10n_mx_edi_pac_status': self.l10n_mx_edi_pac_status,
            'l10n_mx_edi_sat_status': self.l10n_mx_edi_sat_status,
            'l10n_mx_cfdi_uuid': self.l10n_mx_edi_cfdi_uuid,
            'l10n_mx_edi_cfdi_supplier_rfc': self.l10n_mx_edi_cfdi_supplier_rfc,
            'l10n_mx_edi_cfdi_customer_rfc': self.l10n_mx_edi_cfdi_customer_rfc,
            'account_id': self.partner_id.property_account_payable_id.id,
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

            'refund_invoice_id': self.refund_invoice_id.id if self.refund_invoice_id is not False else False,
            'origin': self.refund_invoice_id.number if self.refund_invoice_id is not False else False
        }

    def create_invoice(self):
        inv_obj = self.env['account.invoice']

        values = self.get_invoice_creation_values()

        invoice = inv_obj.with_context({
            'type': values.get('type', 'out_invoice'),
            'default_type': values.get('type', 'out_invoice'),
        }).create(values)

        filename = ('%s-%s-MX-Invoice-%s.xml' % (
            invoice.journal_id.code, invoice.reference, self.version.replace('.', '-'))).replace('/', '')
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

        if self.invoice_state == 'done':
            invoice.action_invoice_open()

        return invoice

    @api.multi
    def action_import(self):
        # create invoice here

        if self.validate_import():
            return self.create_invoice()

    def do_finish_action(self):
        if self.invoice_id.id or True:
            action = self.env.ref('account.action_invoice_tree1').read()[0]

            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = self.invoice_id.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def process_xml_file(self, refresh=True):

        try:
            xml = fromstring(base64.b64decode(self.xml_file))
            self.xml_content = etree.tostring(xml, pretty_print=True)
        except Exception:
            raise ValidationError('Unable to parse XML file')

        self.version = xml.attrib.get('Version')
        self.name = "{}/{}".format(xml.attrib.get('Serie'), xml.attrib.get('Folio'))
        self.date_invoice = datetime.strptime(xml.attrib.get('Fecha'), '%Y-%m-%dT%H:%M:%S') if xml.attrib.get(
            'Fecha') else False
        self.currency_code = xml.attrib.get('Moneda')
        self.exchange_rate = xml.attrib.get('TipoCambio', 1)
        self.l10n_mx_edi_cfdi_amount = float(xml.attrib.get('Total', xml.attrib.get('total', 0)))

        self.invoice_type = 'in_invoice' if xml.attrib.get('TipoDeComprobante', 'I').upper() == 'I' else 'in_refund'

        self.amount_untaxed = float(xml.attrib.get('SubTotal', xml.attrib.get('subTotal', 0)))
        self.amount_total = float(xml.attrib.get('Total', xml.attrib.get('total', 0)))

        taxes_section = getattr(xml, 'Impuestos', False)
        if isinstance(taxes_section, ObjectifiedElement):
            self.amount_tax = float(taxes_section.attrib.get('TotalImpuestosTrasladados', 0))

        self.payment_term_name = xml.attrib.get('CondicionesDePago') or ''

        self.l10n_mx_edi_cfdi_supplier_name = xml.Receptor.attrib.get('Nombre', xml.Receptor.attrib.get('nombre'))
        self.l10n_mx_edi_cfdi_supplier_rfc = xml.Receptor.attrib.get('Rfc', xml.Receptor.attrib.get('rfc'))
        self.l10n_mx_edi_cfdi_customer_name = xml.Emisor.attrib.get('Nombre', xml.Emisor.attrib.get('nombre'))
        self.l10n_mx_edi_cfdi_customer_rfc = xml.Emisor.attrib.get('Rfc', xml.Emisor.attrib.get('rfc'))

        self.l10n_mx_edi_usage = xml.Receptor.attrib.get('UsoCFDI')

        complemento_section = getattr(xml, 'Complemento', False)

        timbre = complemento_section.find('tfd:TimbreFiscalDigital', EDI_NAMESPACES) if complemento_section else False

        if isinstance(timbre, StringElement):
            self.l10n_mx_edi_cfdi_uuid = timbre.get('UUID')

            if self.l10n_mx_edi_cfdi_uuid:
                self.l10n_mx_edi_pac_status = 'signed'
                self.l10n_mx_edi_sat_status = 'valid'

        concepts_section = getattr(xml, 'Conceptos', False)

        if refresh is False and isinstance(concepts_section, ObjectifiedElement):
            AccountTax = self.env['account.tax']

            lines = []
            for i in range(concepts_section.countchildren()):
                item = concepts_section.Concepto[i]
                line = self._get_invoice_line_from_xml(item)

                lines.append((0, 0, line))

            self.line_ids = lines

            if taxes_section:
                tax_lines = []
                transfers_section = getattr(taxes_section, 'Traslados', False)

                if isinstance(transfers_section, ObjectifiedElement):

                    for i in range(transfers_section.countchildren()):
                        item = transfers_section.Traslado[i]
                        importe = float(item.attrib.get('Importe', item.attrib.get('importe', 0)))
                        impuesto = item.attrib.get('Impuesto', item.attrib.get('impuesto', False))
                        tasa = float(item.attrib.get('TasaOCuota', item.attrib.get('tasa', 0))) * 100
                        tax_item = AccountTax.search([('amount', '=', tasa), ('type_tax_use', '=', 'purchase')], limit=1)

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

        if self.invoice_type == 'in_refund':
            # cfdi: CfdiRelacionados
            related_section = getattr(xml, 'CfdiRelacionados', False)

            if isinstance(related_section, ObjectifiedElement):
                self.l10n_mx_edi_redunded_invoice_cfdi_uuid = related_section.CfdiRelacionado.attrib.get('UUID')

                if not self.refund_invoice_id.id:
                    raise MissingRelatedUUIDError(_('Missing Related UUID %s in XML') % (
                            self.l10n_mx_edi_redunded_invoice_cfdi_uuid,),
                        uuid=self.l10n_mx_edi_redunded_invoice_cfdi_uuid)

        if self.l10n_mx_edi_cfdi_uuid:
            uuid_search = self.env['account.invoice'].sudo().search([('l10n_mx_cfdi_uuid', '=', self.l10n_mx_edi_cfdi_uuid)])
            if uuid_search:
                raise DuplicateUUIDError(
                    _('Duplicated UUID %s') % (
                        self.l10n_mx_edi_cfdi_uuid,),
                    uuid=self.l10n_mx_edi_cfdi_uuid)

        if not self.company_id:
            raise MissingCompanyError(
                _('Unable to find company %s with RFC %s') % (
                    self.l10n_mx_edi_cfdi_supplier_name, self.l10n_mx_edi_cfdi_supplier_rfc),
                name=self.l10n_mx_edi_cfdi_supplier_name, rfc=self.l10n_mx_edi_cfdi_supplier_rfc)

        # if self.company_id.id != self.env.user.partner_id.company_id.id:
        if self.company_id.id not in self.env.user.company_ids.mapped('id') + [self.env.user.partner_id.company_id.id]:
            raise InvalidCompanyError(
                _('Unable to process XML from company other than "%s" with RFC "%s". Invoice RFC: "%s".') % (
                    self.env.user.partner_id.company_id.name, self.env.user.partner_id.company_id.vat,
                    self.company_id.partner_id.vat),
                user_company=self.env.user.partner_id.company_id, invoice_company=self.company_id
            )

        if not self.partner_id:
            raise MissingPartnerError(
                _('Unable to find client "%s" with RFC "%s".') % (
                    self.l10n_mx_edi_cfdi_customer_name, self.l10n_mx_edi_cfdi_customer_rfc),
                name=self.l10n_mx_edi_cfdi_customer_name, rfc=self.l10n_mx_edi_cfdi_customer_rfc)

        if not self.currency_id:
            raise InvalidCurrencyError(
                _('Unable to find currency "%s".') % (self.currency_code, ),
                currency_code=self.currency_code)

        invalid_lines = filter(lambda p: not p.product_id, self.line_ids)

        if len(list(invalid_lines)):
            raise InvalidProductLinesError(_('Some invoice lines doesnt have a valid product associated.'))

        return True

    def _get_invoice_line_from_xml(self, item):
        AccountTax = self.env['account.tax']

        tax_ids = []
        total_taxes = 0
        if self.version == '3.3':
            if hasattr(item, 'Impuestos') and hasattr(item.Impuestos, 'Traslados'):
                for tIndex in range(item.Impuestos.Traslados.countchildren()):

                    concept_tax_section = getattr(item, 'Impuestos')

                    if concept_tax_section:
                        tax = concept_tax_section.Traslados.Traslado[0]
                        if tax.attrib.get('TasaOCuota'):

                            tasa = float(tax.attrib['TasaOCuota']) * 100
                            total_taxes += float(tax.attrib.get('Importe', 0))

                            tax_item = AccountTax.search([('amount', '=', tasa), ('type_tax_use', '=', 'purchase')], limit=1)

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

        return line

    @api.multi
    def action_create_partner(self):
        view = self.env.ref('base.view_partner_form')

        return {
            'name': _('Vendor'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.partner',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': {
                'default_name': self.l10n_mx_edi_cfdi_customer_name,
                'default_vat': self.l10n_mx_edi_cfdi_customer_rfc,
            }
        }

    @api.multi
    def action_enable_currency(self):
        self.ensure_one()

        if self.currency_code and not self.currency_id.id:
            Currency = self.env['res.currency'].sudo()

            toEnable = Currency.search([('name', '=', self.currency_code), ('active', '=', False)])

            if toEnable:
                toEnable.active = True

                self.currency_id = toEnable.id

                return False

            else:
                raise UserError(_("The specified currency '{currency}' doesn't exist in the system").format(
                    currency=self.currency_code))


class MissingCompanyError(UserError):
    def __init__(self, msg, name, rfc):
        super(MissingCompanyError, self).__init__(msg)
        self.company_name = name
        self.company_rfc = rfc


class InvalidCompanyError(UserError):
    def __init__(self, msg, user_company, invoice_company):
        super(InvalidCompanyError, self).__init__(msg)
        self.user_company = user_company
        self.invoice_company = invoice_company


class InvalidCurrencyError(UserError):
    def __init__(self, msg, currency_code):
        super(InvalidCurrencyError, self).__init__(msg)
        self.currency_code = currency_code


class DuplicateUUIDError(UserError):
    def __init__(self, msg, uuid):
        super(DuplicateUUIDError, self).__init__(msg)
        self.uuid = uuid


class MissingRelatedUUIDError(UserError):
    def __init__(self, msg, uuid):
        super(MissingRelatedUUIDError, self).__init__(msg)
        self.uuid = uuid


class InvalidProductLinesError(UserError):
    def __init__(self, msg):
        super(InvalidProductLinesError, self).__init__(msg)


class MissingPartnerError(UserError):
    def __init__(self, msg, name, rfc):
        super(MissingPartnerError, self).__init__(msg)
        self.partner_name = name
        self.partner_rfc = rfc
