{
    'name': 'Product Multi Image Upload',
    'version': '1.0',
    'depends': ['product', 'web', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/upload_img.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wz_multi_upload_img/static/src/js/multi_upload.js',
            'wz_multi_upload_img/static/src/xml/multi_upload.xml',
        ],
    },
}