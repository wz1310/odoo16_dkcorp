{
    'name': 'Inherit Sale and Transfer',
    'summary': """Inherit Sale and Transfer""",
    'version': '0.0.1',
    'author': 'Wiza',
    'description': """Inherit Sale and Transfer""",
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/transfer_inherit_view.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True
}