{
    'name': 'Inherit MRP Matrix',
    'summary': """Inherit MRP Matrix""",
    'version': '0.0.1',
    'author': 'Wiza',
    'description': """Inherit MRP Matrix""",
    'depends': ['contacts','mrp','approval_matrix', 'web_many2one_reference'],
    'data': [
        'views/mo_view.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True
}