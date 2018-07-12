# -*- coding: utf-8 -*-
{
    'name': "Blueline Custom Invoice External Trade integration",

    'summary': """
        Custom Invoice Report For Mexican Accounting ( External Trade integration )""",

    'description': """
        Blueline Custom Invoice Report For Mexican Accounting ( External Trade integration ) 
    """,

    'author': "Yusnel Rojas Garcia",
    'website': "http://www.local.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Invoicing Management',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['l10n_mx_edi_external_trade_bluemix', 'blueline_l10n_mx_custom_invoice'],

    # always loaded
    'data': [
        'data/3.3/cfdi.xml',
        'views/templates.xml',
    ],

    'auto_install': True
}