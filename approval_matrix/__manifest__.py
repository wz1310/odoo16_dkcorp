# -*- coding: utf-8 -*-
{
    'name': "approval_matrix",

    'summary': """
        Approval Matrix for any model""",

    'description': """
        Approval Matrix for any model. You just only need call approval_matrix_validation()
    """,

    'author': "Portcities",
    'website': "http://www.portcities.net",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'approval',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','web_many2one_reference','hr','sale'],

    # always loaded
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',

        'views/approval_matrix.xml',
        'views/approval_matrix_document_approval.xml',
        
        'views/rejection_message.xml',
        'views/message_post_wizard.xml',
        
    ],
    # only loaded in demonstration mode
    'demo': [
        
    ],
}