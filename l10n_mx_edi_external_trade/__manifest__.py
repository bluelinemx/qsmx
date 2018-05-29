# -*- coding: utf-8 -*-
{
    'name': "Mexico EDI External Trading",

    'summary': """
    Mexico EDI External Trading""",

    'description': """
        Mexico EDI External Trading
    """,

    'author': "Yusnel Rojas Garcia",
    'website': "http://www.local.com",

    'category': 'Invoicing Management',
    'version': '0.1',

    'depends': ['account', 'l10n_mx_edi'],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',

        'data/xml/product_data.xml',
        'data/xml/customs_uom_data.xml',
        'data/xml/incoterms_data.xml',

        'views/res_partner_view.xml',
        'views/res_company_view.xml',
        'views/account_invoice_view.xml',
        'views/product_view.xml',
        'views/customs_view.xml',
        'views/location_view.xml',

        'views/report_invoice.xml',

        'views/menu.xml',

        'data/cfdi/3.3/cfdi.xml',
    ],

    'post_init_hook': 'post_init_hook',

    'demo': [
        'demo/demo.xml',
    ],
}