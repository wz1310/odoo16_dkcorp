import logging
import datetime

from odoo.tests import common,tagged


_logger = logging.getLogger(__name__)


@tagged('post_install', 'at_install')
class TestApprovalMatrix(common.TransactionCase):
    def setUp(self):
        return super().setUp()
    
    def test_rules_check_is_valid(self):
        res_partner_model = self.env.ref('base.model_res_partner')
        active_res_partner_field = res_partner_model.field_id.filtered(lambda r:r.name=='active')
        matrix = {
            'name':'Test Matrix',
            'company_id':1,
            'model_id':res_partner_model.id,
            'approver_ids':[(0,0,{
                'seq':1,
                'user_ids':[(6,0,[self.env.user.id])],
                'require_all_approver':True,
                'min_approver':1

            })],
            'rule_ids':[
                (0,0,{
                    'field_id':active_res_partner_field.id,
                    'operator':'=',
                    'value':'0',
                })
            ]
        }
        TestMatrix = self.env['approval.matrix'].create(matrix)
        self.assertEqual(TestMatrix.id!=False,True)

        Contact = self.env['res.partner'].create({
            'active':False,
            'name':"new Contact",
            'state':'draft'
        })
        self.assertEqual(Contact.id!=False,True)
        findmatrix = self.env['approval.matrix'].find_possible_matrix(1, 'res.partner', Contact)

        