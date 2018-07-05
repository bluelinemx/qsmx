# -*- coding: utf-8 -*-
{
    'name': "QSMX Web Modifications",

    'description': """
        QSMX Web Modifications
    """,

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'views/views.xml',
        'views/templates.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
}