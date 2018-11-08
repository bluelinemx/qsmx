# -*- coding: utf-8 -*-
{
    'name': "Mexico Bulk Provider XML Invoice Import",

    'summary': """
        Mexico Bulk Provider XML Invoice Import""",

    'description': """
        Allow to import multiple provider xml files into vendor bills
    """,

    'author': "Yusnel Rojas Garcia",
    'website': "",

    'category': 'Invoicing Management',
    'version': '0.1',

    'depends': ['l10n_mx', 'l10n_mx_edi', 'stock'],

    'data': [
        # 'security/ir.model.access.csv',
        'wizard/l10n_mx_bulk_import_wizard_view.xml',
        'views/views.xml',
        'views/templates.xml',
    ]
}

