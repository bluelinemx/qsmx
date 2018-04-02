# -*- coding: utf-8 -*-
{
    'name': "Mexico EDI Import",

    'summary': """
        Allow to import edi xml files into invoices""",

    'description': """
        Allow to import edi xml files into invoices
    """,

    'author': "Yusnel Rojas Garcia",
    'website': "",

    'category': 'Invoicing Management',
    'version': '0.1',

    'depends': ['l10n_mx_edi'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/l10n_mx_edi_import_wizard_view.xml',
        'views/views.xml',
        'views/templates.xml',
    ]
}

