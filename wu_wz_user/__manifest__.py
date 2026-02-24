{
    'name': 'Inherit user Custom',
    'summary': """Inherit user""",
    'version': '0.0.1',
    'author': 'Wiza',
    'description': """Inherit User""",
    'depends': ['contacts','sale','approval_matrix', 'web_many2one_reference','stock'],
    'data': [
        'views/user_view.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True
}