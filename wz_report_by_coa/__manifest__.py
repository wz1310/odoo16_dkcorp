{
    'name': 'Inherit COA ',
    'summary': """Inherit COA """,
    'version': '0.0.1',
    'author': 'Wiza',
    'description': """Inherit COA """,
    'depends': ['account','sale','stock','wz_multi_upload_img'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/financial_report_wizard_view.xml',
        'views/inher_picking.xml',
        'views/mrp_worker_views.xml',
        'views/coa_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True
}