# -*- coding: utf-8 -*-
{
    'name': "Blueline Custom Invoice",

    'summary': """
        Custom Invoice Report For Mexican Accounting""",

    'description': """
        Blueline Custom Invoice Report For Mexican Accounting
    """,

    'author': "Softpei, Ingenieria y Sistemas",
    'website': "http://www.softpei.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Invoicing Management',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'web', 'l10n_mx_edi'],

    # always loaded
    'data': [
        'data/data.xml',
        'data/3.3/cfdi.xml',
        'data/3.2/cfdi.xml',
        'views/view.xml',
        'views/templates.xml',
    ],
}