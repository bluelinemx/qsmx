# -*- coding: utf-8 -*-

import base64
import io

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import etree, zipfile
import os.path


class EdiBulkImportFile(models.TransientModel):
    _inherit = 'l10n.mx.provider.xml.bulk.import.invoice'

    wizard_id = fields.Many2one('l10n.mx.xml.bulk.import.wizard', ondelete='CASCADE')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], string='Status', default='pending')

    error_code = fields.Selection([
        ('DuplicateUUIDError', 'Duplicate UUID'),
        ('MissingCompanyError', 'Missing Company'),
        ('InvalidCompanyError', 'Invalid Company'),
        ('InvalidCurrencyError', 'Invalid Currency'),
        ('MissingPartnerError', 'Missing Provider'),
        ('InvalidProductLinesError', 'Invalid Products'),
        ('MissingRelatedUUIDError', 'Missing Invoice'),
    ], string='Error Code')

    error_description = fields.Char('Error Description')

    @api.multi
    def action_enable_currency(self):
        result = super().action_enable_currency()

        return self.wizard_id.action_preview_import(refresh=True)

    @api.multi
    def action_open_invoice(self):
        if self.invoice_id.id or True:
            action = self.env.ref('account.action_invoice_tree2').read()[0]

            action['views'] = [(self.env.ref('account.invoice_supplier_form').id, 'form')]
            action['res_id'] = self.invoice_id.id
            action['target'] = 'new'

            ctx = dict(self._context or {})

            ctx.update({
                'active_model': self.wizard_id._name,
                'active_id': self.wizard_id.id,
            })

            action['context'] = ctx
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


class EdiBulkImport(models.TransientModel):
    _name = 'l10n.mx.xml.bulk.import.wizard'

    file_name = fields.Char()
    zip_file = fields.Binary(required=True, string='Zip or XML File')
    file_ids = fields.One2many('l10n.mx.provider.xml.bulk.import.invoice', 'wizard_id', string='Files')

    files_count = fields.Integer('Count', compute='_compute_file_count')
    error_count = fields.Integer('Errors', compute='_compute_error_count')
    valid_count = fields.Integer('Valid', compute='_compute_error_count')
    can_import = fields.Boolean('Can Import', compute='_compute_error_count')

    @api.one
    @api.depends('file_ids')
    def _compute_file_count(self):
        self.files_count = len(self.file_ids)

    @api.one
    @api.depends('file_ids', 'file_ids.state')
    def _compute_error_count(self):
        self.error_count = len([line for line in self.file_ids if line.state == 'error'])
        self.valid_count = len([line for line in self.file_ids if line.state != 'error'])
        self.can_import = self.valid_count > 0

    @api.multi
    def action_next(self):
        name, ext = [p.lower() for p in os.path.splitext(self.file_name)]

        if ext not in ['.zip', '.xml']:
            raise UserError(_('Only zip and xml files are allowed.'))

        if ext == '.zip':
            return self.process_zip_file()
        elif ext == '.xml':
            return self.process_xml_file()

    @api.multi
    def action_import(self):
        if not self.can_import:
            raise UserError(_('There are not valid files to import. Please fix the errors and refresh or upload another set of files'))

        for line in self.file_ids:
            try:
                if line.validate_import():
                    invoice = line.create_invoice()

                line.state = 'done'
            except Exception as e:
                line.state = 'error'

        return self.action_import_results()

    @api.multi
    def action_upload(self):
        upload_form = self.env.ref('l10n_mx_bulk_provider_xml_import.bulk_import_wizard_form')

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

    @api.multi
    def action_refresh(self):
        return self.action_preview_import(refresh=True)

    @api.multi
    def action_finish(self):
        ids = self.file_ids.filtered(lambda l: l.state == 'done').mapped('invoice_id.id')

        action = self.env.ref('account.action_invoice_tree2').read()[0]
        action['target'] = 'main'
        action['domain'] = [('id', 'in', ids)]

        return action

    def action_preview_import(self, refresh=False):
        if len(self.file_ids) == 0:
            raise UserError(_('There are no files to process. Please go back and upload a zip or xml file.'))

        for line in self.file_ids:
            try:
                result = line.action_validate(refresh=refresh)

                line.state = 'pending'
                line.error_code = False
                line.error_description = False
            except UserError as e:
                line.state = 'error'
                line.error_code = type(e).__name__
                line.error_description = e.name

        preview_form = self.env.ref('l10n_mx_bulk_provider_xml_import.bulk_import_wizard_preview_form')

        return {
            'name': _('Preview Files'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': self._name,
            'views': [(preview_form.id, 'form')],
            'view_id': preview_form.id,
            'target': 'new',
        }

    def action_import_results(self):
        preview_form = self.env.ref('l10n_mx_bulk_provider_xml_import.bulk_import_wizard_results_form')

        return {
            'name': _('Import Results'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': self._name,
            'views': [(preview_form.id, 'form')],
            'view_id': preview_form.id,
            'target': 'new',
        }

    def process_zip_file(self):
        try:
            file_like_object = io.BytesIO(base64.decodebytes(self.zip_file))
        except Exception:
            raise ValueError(self.zip_file)

        zf = zipfile.ZipFile(file_like_object)

        xml_files = [p for p in zf.namelist() if os.path.splitext(p)[1].lower() == '.xml']

        if not xml_files:
            UserError(_('No xml files found in the zip file'))

        FileModel = self.env['l10n.mx.provider.xml.bulk.import.invoice']

        for item in xml_files:
            zitem = zf.read(item)

            FileModel.create({
                'wizard_id': self.id,
                'invoice_type': 'in_invoice',
                'invoice_state': 'draft',
                'xml_filename': item,
                'xml_file': base64.b64encode(zitem),
            })

        return self.action_preview_import(refresh=False)

    def process_xml_file(self):

        FileModel = self.env['l10n.mx.provider.xml.bulk.import.invoice']

        FileModel.create({
            'wizard_id': self.id,
            'invoice_type': 'in_invoice',
            'invoice_state': 'draft',
            'xml_filename': self.file_name,
            'xml_file': self.zip_file,
        })

        return self.action_preview_import(refresh=False)