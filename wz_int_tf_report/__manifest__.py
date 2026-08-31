# -*- coding: utf-8 -*-

{
    'name': 'WZ Internal Report Form',
    'version': '1.0',
    'category': '',
    'sequence': 6,
    'author': 'WZ',
    'summary': 'Allows you to print report pdf.',
    'description': "Allows you to print report pdf.",
    'depends': ['stock'],
    'data': [
        'report/paper_format.xml',
        'report/ir_actions_report.xml',
        'views/stock_picking.xml',
        # 'views/report_action.xml',
        'report/report_delivery_template.xml'
    ],
    'installable': True,
    'website': '',
    'auto_install': False,
}
