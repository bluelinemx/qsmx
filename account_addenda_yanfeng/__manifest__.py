{
    'name': 'Addenda Yanfeng',
    'version': '11.0',
    'category': '',
    'summary': 'Modulo para Agregar Addenda de Yanfeng a la Factura.',
    'author': 'Xmarts',
    'depends': ['account','contacts','l10n_mx_edi'],
    'data': [
        'views/res_partner.xml',
        'views/account_invoice.xml',
        'data/yanfeng_addenda.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
