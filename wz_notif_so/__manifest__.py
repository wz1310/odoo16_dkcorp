{
    'name': 'WZ Notif Sale Order',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Notifikasi Manager Approval untuk Sale Order',
    'depends': ['base', 'web', 'sale'],
    'data': [
        'security/res_security.xml',
        'views/notif_so_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wz_notif_so/static/src/js/so_notification.js',
            'wz_notif_so/static/src/xml/so_notification_template.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}