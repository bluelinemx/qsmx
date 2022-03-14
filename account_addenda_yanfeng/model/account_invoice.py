from odoo import fields, models, api


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    ref_orden_compra = fields.Char(string="Orden de Compra", copy=False)

