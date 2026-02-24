{
    'name': 'WZ Remove Qty 0 Delivery Slip',
    'version': '16.0.1.0.0',
    'category': 'Inventory',
    'summary': 'WZ Remove Qty 0 Delivery Slip',
    'author': 'WZ',
    'depends': [
        'stock', 
        'mstl_report'
    ],
    'data': [
        'report/remove_zero.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}