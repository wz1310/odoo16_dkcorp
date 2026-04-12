{
    'name': 'Inherit Sale Matrix',
    'summary': """Inherit Sale Matrix""",
    'version': '0.0.1',
    'author': 'Wiza',
    'description': """Inherit Sale Matrix""",
    'depends': ['contacts','sale','sale_management','approval_matrix', 'web_many2one_reference'],
    'data': [
        'views/sale_view.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True
}