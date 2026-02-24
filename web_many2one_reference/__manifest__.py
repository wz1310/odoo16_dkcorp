{
    'name': 'Many2one Reference Field',
    'summary': """
        Many2one Reference Field
        """,
    'version': '0.0.1',
    'category': 'web,many2one',
    'author': 'La Jayuhni Yarsyah',
    'description': """
        Many2one reference fields
    """,
    'depends': [
        'web',
    ],
    'assets': {
        'web.assets_backend': [
            'web_many2one_reference/static/srcfields.js',
        ]
    },
    'data': [
        # 'views/assets.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True
}