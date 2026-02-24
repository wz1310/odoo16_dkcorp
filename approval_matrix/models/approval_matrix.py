from odoo import api, fields, models, _
from odoo.exceptions import UserError,ValidationError
import operator as Operator

import xml.etree as etr
import xml.etree.ElementTree as ET

import logging
_logger = logging.getLogger(__name__)


class ApprovalMatrixTag(models.Model):
    _name = 'approval.matrix.tag'
    _description = "approval.matrix.tag"

    name = fields.Char(string="Code",required=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade', index=True)

    _sql_constraints = [
        ('name_unique', 'unique (name)', 'Code must be unique'),
    ]


class ApprovalMatrix(models.Model):
    _name = "approval.matrix"
    _description = "Approval Matrix"

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one('res.company', string="Company", required=True,   default=False, domain=False)
    model_id = fields.Many2one('ir.model', string="Model", required=True,  ondelete='cascade', default=False, domain=[])

    res_model = fields.Char("Res Model")

    rule_ids = fields.One2many('approval.matrix.rule', 'matrix_id', string="Matrix")
    approver_ids = fields.One2many('approval.matrix.approver', 'matrix_id', string="Approvers")
    active = fields.Boolean(string="Active", default=True)

    dept_manager_as_approver = fields.Boolean(string="Dept. Manager as Approver", default=False)
    user_request_field_id = fields.Many2one('ir.model.fields', string="User Requester Field")
    tag_id = fields.Many2one('approval.matrix.tag', string="Approval Matrix Tag")
    tag_code = fields.Char(related="tag_id.name", readonly=True)

    @api.constrains('res_model','model_id')
    def constrains_model(self):
        for rec in self:
            if not rec.model_id.id and rec.res_model:
                res_model = rec._get_model(rec.res_model)
                if not len(res_model):
                    raise UserError(_("Model %s not exist!") % (rec.res_model))
                rec.model_id = res_model.id
            elif rec.model_id.id and not rec.res_model:
                rec.res_model = rec.model_id.model
            

    def _get_model(self, model):
        return self.env['ir.model'].with_user(1).search([('model','=',self.res_model)])

    @api.onchange('res_model')
    def _onchange_model(self):
        res = False
        if self.res_model:
            res_model = self._get_model(self.res_model)
            if len(res_model):
                res = res_model.id
        self.model_id = res

    @api.depends('model_id')
    def _compute_model(self):
        for rec in self:
            rec.model = rec.model_id.model

    def _inverse_model(self):
        for rec in self:
            model = self._get_model(rec.model)
            rec.model_id = model.id

    @api.constrains('dept_manager_as_approver')
    def constrains_dept_manager_as_approver(self):
        for rec in self:
            if rec.dept_manager_as_approver==True:
                if not rec.user_request_field_id.id:
                    raise ValidationError(_("User Requester Field Required!"))

    _constraints = [
        ('name_unique', 'unique (name)', 'Name must be unique'),
    ]


    def _prepare_approval_matrix_document(self, model, record, approver, uid=None):

        if approver and approver.id:
            approver_ids = [(6,0,approver.user_ids.ids)]
        else:
            if not uid:
                raise UserError(_("User manager not found!"))
            approver_ids = [(6,0,[uid])]
        
        res = {
            'res_model_id': model.id,
            'res_id': record.id,
            'matrix_id': approver.matrix_id.id if approver and approver.id else False,
            'approver_seq': approver.seq if approver and approver.id else 0,
            'approver_ids': approver_ids,
            'approved_by_ids': [],
            'rejected_by_ids': [],
            'minimum_approved': approver.min_approver if approver and approver.id else 1,
            'approved_count': 0,
            'rejected_count': 0,
            'approved': False,
        }
        return res

    def fetch_manager_user_by_uid(self,uid):
        query = """
        SELECT hrmanager.user_id FROM hr_employee he
        JOIN hr_department AS hd on hd.id = he.department_id
        JOIN hr_employee AS hrmanager ON hrmanager.id = hd.manager_id
        WHERE he.user_id = %s
        """

        self.env.cr.execute(query, (uid,))
        res = self.env.cr.fetchall()

        ids = [row[0] for row in res]
        if len(ids):
            return ids[0]


    @api.model
    def generate_approval_docs(self,model,record):
        
        for rec in self:
            
            if rec.dept_manager_as_approver:
                
                # required 
                field_requester_value = getattr(record, rec.user_request_field_id.name)
                
                # if has value
                if field_requester_value.id:
                    manager_user_id = self.fetch_manager_user_by_uid(field_requester_value.id)
                    new_approvals = self._prepare_approval_matrix_document(model, record, approver=False, uid=manager_user_id)
                    
                    self.env['approval.matrix.document.approval'].create(new_approvals)
            else:
                # fetch approval by lines
                new_approvals = []
                for approver in rec.approver_ids:
                    new_approvals.append(self._prepare_approval_matrix_document(model, record, approver))
                
                if len(new_approvals):
                    self.env['approval.matrix.document.approval'].create(new_approvals)

    # model_name = fields.Char(related="model_id.model", string="ModelName", store=True)
    # domain = fields.Char("Domain")
    # NORMAL USAGE
    @api.model
    def find_possible_matrix(self, company, model, record):
        
        domain = [('model_id','=',model.id)]
        _logger.info(("find_possible_matrix with domain", domain))
        force_company = self._context.get('force_company',None)
        
        if  force_company != None:
            if force_company==False:
                _logger.info(("Finding possible matrix without company domain"))
            else:
                domain.append((('company_id','in',company.ids)))
        else:
            domain.append(('company_id','in',company.ids))
        

        # if has tag
        if self._context.get('tag'):
            domain.append(('tag_code','=','so.non.agreement'))
        else:
            domain.append(('tag_id','=',False))

        # if has existing
        # then will exclude exisiting
        if len(record.approval_ids):
            domain.append(('id','not in', record.approval_ids.ids))
        
        matrixs = self.search(domain)
        _logger.info(("Found matrix to check:%s with domain: %s" % (matrixs, domain)))
        res = self.env[self._name]
        for matrix in matrixs:
            check_matrix = matrix.rule_ids._check_is_valid(record)
            _logger.info('checking matrix %s is match to rules:%s' % (matrix.display_name, check_matrix))
            if check_matrix:
                res += matrix
        return res


    # UNCOMMENT THIS IF USING DOMAIN WIDGET
    # @api.model
    # def find_possible_matrix(self, company, model, record):
        
    #     domain = [('model_id','=',model.id)]
    #     force_company = self._context.get('force_company',None)
    #     if  force_company != None:
    #         if force_company==False:
    #             _logger.info(("Finding possible matrix without company domain"))
    #         else:
    #             domain.append((('company_id','in',company.ids)))
    #     else:
    #         domain.append(('company_id','in',company.ids))
    #     # find all same model in company
    #     matrixs = self.search(domain)
    #     res = self.env[self._name]
    #     for m in matrixs:
    #         l_domain = list(eval(m.domain))
    #         # _logger.info((m.domain, type(m.domain), l_domain[0]))
    #         filtered_rec = self.env[m.model_name].search(l_domain)
    #         if record.id in filtered_rec.ids:
    #             res += m
    #     # res = self.env[self._name]
    #     # for matrix in matrixs:
    #     #     if matrix.rule_ids._check_is_valid(record):
    #     #         res += matrix
        
    #     return res


class ApprovalMatrixRule(models.Model):
    _name = "approval.matrix.rule"
    _description = "Approval Matrix Rule"

    matrix_id = fields.Many2one('approval.matrix', string="Matrix", required=True,   default=False, domain=[])
    company_id = fields.Many2one(related="matrix_id.company_id", store=True, readonly=True)
    model_id = fields.Many2one(related="matrix_id.model_id", readonly=True)
    field_id = fields.Many2one('ir.model.fields', string="Field", required=True, ondelete='cascade',  default=False, domain=[])
    
    operator = fields.Selection([('=','='), ('!=','!='), ('<','<'), ('<=','<='), ('>','>'), ('>=','>=')], string="operator", default='=', required=True)
    value = fields.Char(string="Value", required=True)

    related_field_model = fields.Char(string="Related Model", related="field_id.relation", store=True, compute_sudo=True)
    m2o_value_id = fields.Integer("Relation Val", required=False)
    m2o_value = fields.Char("Relation Val", compute="_compute_m2o_value", compute_sudo=True)

    # @api.onchange('value','field_id')
    # def _onchange_field_value(self):
    #     if self.field_id.id and self.value:
    #         if self.field_id.relation:
    #             self.m2o_value_id = self.value

    #     return {
    #         'domain':{
    #             'm2o_value_id':[('id','=',)]
    #         }
    #     }
    @api.onchange('m2o_value_id')
    def _onchange_m2o_value_id(self):
        if self.m2o_value_id > 0:
            self.value = self.m2o_value_id
        else:
            self.value = False

    @api.depends('m2o_value_id')
    def _compute_m2o_value(self):
        for rec in self:
            
            if rec.m2o_value_id:
                
                rec.m2o_value = "%s,%s" % (rec.field_id.relation, rec.m2o_value_id)
                
            else:
                
                rec.m2o_value = False


    OPERATORS = {
        '=' : Operator.eq,
        '!=': Operator.ne,
        '<': Operator.lt,
        '<=': Operator.le,
        '>': Operator.gt,
        '>=': Operator.ge,
    }

    @api.model
    def _check_is_valid(self, record):
        def value_operator(value, operator):
            if operator not in ['=','!=']:
                return float(value)
            else:
                return str(value)

        # same_header = len(self.mapped("matrix_id")) == 1
        # if not same_header:
        #     raise ValidationError(_("Not Allowed checking rules on various header!"))
        
        rules = []
        for rec in self:
            
            value_to_compare = getattr(record, rec.field_id.name)
            _logger.info(('checking', value_to_compare))
            if rec.field_id.ttype=='boolean':
                
                if rec.value in ['True','true','1']:
                    bool_value = True
                else:
                    bool_value = False
                _logger.info("comparing field %s value %s with %s" % (rec.field_id.display_name, bool_value, value_to_compare))
                # fun = Operator.truth
                # rules.append(fun(value_operator(value_to_compare, rec.operator)))
                rules.append(value_to_compare == bool_value)

                
                
            elif rec.field_id.ttype=='many2one':
                try:
                    fun = rec.OPERATORS.get(rec.operator)
                    rules.append(fun(value_to_compare.id,rec.m2o_value_id))
                except Exception as e:
                    _logger.info("checking rules(%s) for many2one field (%s) raise an exception: %s" % (rec.matrix_id.display_name, rec.field_id.display_name,str(e)))
                    rules.append(False)
            else:
                fun = rec.OPERATORS.get(rec.operator)
                
                rules.append(fun(value_operator(value_to_compare, rec.operator),value_operator(rec.value, rec.operator)))
                
        if not all(rules):
            _logger.warning(("Rules warn: ",rules))
        else:
            _logger.info("Rules passed %s" % str((rules)))
        
        return all(rules)


class ApprovalMatrixApprover(models.Model):
    _name = "approval.matrix.approver"
    _description = "Approval Matrix Approver"

    seq = fields.Integer(stirng="Level", required=True)
    matrix_id = fields.Many2one('approval.matrix', string="Matrix", required=True,   default=False, domain=[])
    user_ids = fields.Many2many('res.users', 'approval_matrix_rule_approver_res_users_rel', 'approval_matrix_rule_approver_id', 'res_users_id', string="Users")
    require_all_approver = fields.Boolean(string="Required All Approver", default=True, help="If this checked, related doc require all approval from listed users")
    min_approver = fields.Integer(string="Min Approver", required=True, default=1)

    @api.constrains('min_approver')
    def _constrains_min_approver(self):
        for rec in self:
            if rec.require_all_approver==False and rec.min_approver<=0:
                raise UserError(_("Minimum Approver not valid!"))
            else:
                if rec.require_all_approver and rec.min_approver==0:
                    rec.min_approver = len(rec.user_ids)
                elif rec.min_approver > len(rec.user_ids):
                    raise UserError(_("Min Approver More than number of user. Not Valid!"))
        return True

    @api.onchange('user_ids')
    def onchange_user_ids(self):
        
        self.min_approver = len(self.user_ids)

    @api.onchange('require_all_approver','min_approver')
    def _onchange_require_all_approver(self):
        res = {}
        if self.require_all_approver==True:
            
            self.update({'min_approver':len(self.user_ids)})
        else:
            if not self.min_approver:
                self.min_approver = 1
            
        return res


class ApprovalMatrixMixin(models.AbstractModel):
    _name = 'approval.matrix.mixin'
    _description = 'Approval Matrix Mixin'

    approval_ids = fields.One2many('approval.matrix.document.approval', 'res_id', auto_join=True, groups="base.group_user")
    approved = fields.Boolean("Approved", compute="_compute_approved")

    user_can_approve = fields.Boolean(string="User can approve", compute="_compute_user_can_approve")

    approvers_user_ids = fields.Many2many('res.users', string="Approvers", compute="_compute_approvers", search="_search_approvers")
    approved_by_ids = fields.Many2many('res.users', string="Approved By", compute="_compute_approvers")
    rejected_by_ids = fields.Many2many('res.users', string="Rejected By", compute="_compute_approvers")
    
    minimum_approved = fields.Integer(string="Min Approved", compute="_compute_approvers")
    remaining_approval = fields.Integer(string="Remain. Approval", compute="_compute_approvers")


    def _search_approvers(self, operator, value):
        domains = [('approver_ids',operator,value)]
        domains += [('res_model','=',self._name)]
        
        ApprovalMatrixDocumentApproval = self.env['approval.matrix.document.approval'].search(domains)
        
        return [('id','in',ApprovalMatrixDocumentApproval.mapped('res_id'))]


    def __append_filter(self, root):
        new_filter = ET.Element('filter')
        new_filter.set('name','filter_approval_matrix_my_approval')
        new_filter.set('string','My Approval')
        
        new_filter.set('domain',"[('approvers_user_ids','in',[%s])]" % (self.env.user.id,))
        root.append(new_filter)
        
        return root

    @api.model
    def _fields_view_get(self, view_id=None, view_type='form', toolbar=True, submenu=False):
        
        sup = super()._fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        
        if view_type=='search':
            root_elm = ET.XML("%s" % (sup['arch']))
            
            new_view = self.__append_filter(root_elm)
            
            arch = ET.tostring(new_view)
            
            sup.update({'arch':arch})
        
        return sup


    def reset_approvers(self):
        self.ensure_one()
        self.approval_ids.unlink()

    def open_approvals(self):
        
        action = self.env['ir.actions.act_window'].for_xml_id('approval_matrix', 'action_approval_matrix_document_readonly')
        action.update({
            'context':{'import':False,'delete':False,'create':False, 'unlink':False},
            'domain':[('res_model','=',self._name),('res_id','=',self.ids)],
        })
        return action
    
    def _compute_approvers(self):
        for rec in self:
            approvers_user_ids = rec.approval_ids.mapped('approver_ids')
            approved_by_ids = rec.approval_ids.mapped('approved_by_ids')
            rejected_by_ids = rec.approval_ids.mapped('rejected_by_ids')
            minimum_approved = sum(rec.approval_ids.mapped('minimum_approved'))
            # reject if any rejection
            rejected = any(rec.approval_ids.mapped(lambda r:r.rejected_count>0))
            if rejected:
                remaining_approval = 0
            else:
                remaining_approval = minimum_approved - sum(rec.approval_ids.filtered(lambda r:r.approved==True).mapped('minimum_approved'))
                    


            rec.update({
                'approvers_user_ids':approvers_user_ids,
                'approved_by_ids':approved_by_ids,
                'rejected_by_ids':rejected_by_ids,
                'minimum_approved':minimum_approved,
                'remaining_approval':remaining_approval,
            })

    def add_approver_as_follower(self):
        followers_partner = []
        for approval in self.approval_ids:
            for approver in approval.approver_ids:
                followers_partner.append(approver.partner_id.id)
        self.message_subscribe(partner_ids=followers_partner)

    @api.depends('approval_ids.approved_by_ids','approval_ids.rejected_by_ids')
    def _compute_approved(self):
        for rec in self:
            rec.approved = all(rec.approval_ids.mapped('approved'))

    def _compute_user_can_approve(self):
        for rec in self:
            rec.user_can_approve = any(self.approval_ids.mapped('user_can_approve'))

    
    def approving_matrix(self, post_action=None):
        # fixme
        self.ensure_one()
        if self.approved==False and self.user_can_approve:
            # find
            approver = self.approval_ids.filtered(lambda r:self.env.user.id in r.approver_ids.ids)
            approver.approve()
            if self.approved and post_action:
                getattr(self, post_action)()

    def rejecting_matrix(self):
        # fixme
        self.ensure_one()
        if self.user_can_approve:
            # find
            approver = self.approval_ids.filtered(lambda r:self.env.user.id in r.approver_ids.ids and self.env.user.id not in r.rejected_by_ids.ids and self.env.user.id not in r.approved_by_ids.ids)
            
            approver.reject()

    def _get_model(self):
        model_name = self._name
        model = self.env['ir.model'].with_user(1).search([('model','=',model_name)])
        return model

    
    def _fetch_approval_matrix(self):
        self.ensure_one()
        model = self._get_model()
        matrix = self.env['approval.matrix'].with_context(self._context.copy()).find_possible_matrix(self.company_id, model, self)
        _logger.info(('result finding matrix-->',matrix))
        
        new_approvals = []
        if len(matrix):
            matrix.generate_approval_docs(model, self)
        
        # if len(new_approvals):
        #     approval_lines = self.env['approval.matrix.document.approval'].create(new_approvals)
        #     return approval_lines



    def checking_approval_matrix(self, add_approver_as_follower=True, data={}, require_approver=True, send_notification=True, tag=False, delete_current=True):
        self.ensure_one()
        # finding rules

        if len(self.approval_ids)>0 and delete_current:
            if all(self.approval_ids.mapped(lambda r:len(r.approved_by_ids)==0 or len(r.rejected_by_ids)==0)):
                self.approval_ids.unlink()
            else:
                self.approval_ids.disable()
        
        if len(self.approval_ids)==0 or delete_current==False:
            if not self._context.get('force_approval'):
                self.with_context(tag=tag)._fetch_approval_matrix()
                # if after fetching approval theres no rules fetched and if require approver will be raise an error
                if not len(self.approval_ids) and require_approver==True:
                    company = False
                    try:
                        company = self.company_id.display_name
                    except Exception as e:
                        pass
                    info = [
                        "approval.matrix",
                        "model: %s" % (self._name,),
                        "company: %s" % (company),
                    ]
                    info_str = "\n".join(info)
                    raise ValidationError(_("Rules Required to perform the action. Please Contact Administrator to create the rules for approval!\n%s") % (info_str,))
        
        
        

        if len(self.approval_ids) and add_approver_as_follower:
            self.add_approver_as_follower()
        
        if data:
            self.update(data)
        
        self.approval_ids._send_notification()

class ApprovalMatrixDocumentApproval(models.Model):
    _name = 'approval.matrix.document.approval'
    _description = 'Approval Matrix Document Approval'

    res_model_id = fields.Many2one('ir.model', 'Document Model', index=True, ondelete='cascade', required=True)
    res_model = fields.Char('Related Document Model', index=True, related='res_model_id.model', compute_sudo=True, store=True, readonly=True)
    res_id = fields.Many2oneReference(string='Related Document ID', index=True, required=True, model_field='res_model')
    res_name = fields.Char('Document Name', compute='_compute_res_name', compute_sudo=True, store=True, help="Display name of the related document.", readonly=True)

    matrix_id = fields.Many2one('approval.matrix', required=False, string="Matrix")
    approver_seq = fields.Integer("Approver Level", required=True)
    approver_ids = fields.Many2many('res.users', 'approval_matrix_doc_approval_user_rel', 'approval_id', 'user_id', string="Approvers")
    approved_by_ids = fields.Many2many('res.users', 'approval_matrix_doc_approved_by_rel', 'approval_id', 'user_id', string="Approved By")
    rejected_by_ids = fields.Many2many('res.users', 'approval_matrix_doc_rejected_by_rel', 'approval_id', 'user_id', string="Rejected By")
    minimum_approved = fields.Integer("Min. Approved")
    approved_count = fields.Integer("Approved Count", compute="_compute_approval")
    rejected_count = fields.Integer("Rejected Count", compute="_compute_approval")
    approved = fields.Boolean("Is Approved", compute="_compute_approval")

    user_can_approve = fields.Boolean(string="User can approve", compute="_compute_user_can_approve")
    active = fields.Boolean("Active", default=True)

    def _send_notification(self):
        for rec in self:
            msg = "<big>APPROVAL REQUEST for %s #%s</big><br/>DOC. %s need to review for your approval!" % (rec.res_model_id.name, rec.res_name, rec.res_name)
            if len(rec.approver_ids):
                partner = rec.approver_ids.mapped('partner_id')
                doc = self.env[rec.res_model].browse(rec.res_id)

                try:
                    doc.message_notify(body=msg, partner_ids=partner.ids)
                except Exception as e:
                    _logger.warning(_("Failed to send notification wich model %s not applying activity.mixin") % (rec.res_model,))
                    

    def disable(self):
        self.write({"active":False})

    def _compute_user_can_approve(self):
        # fixme
        for rec in self:
            res = False
            # if user in approved , not been approved, and not in rejected by list

            if self.env.user.id in rec.approver_ids.ids and \
                self.env.user.id not in rec.approved_by_ids.ids and \
                self.env.user.id not in rec.rejected_by_ids.ids:
                res = True
            rec.user_can_approve = res
    
    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for rec in self:
            rec.res_name = rec.res_model and \
                self.env[rec.res_model].browse(rec.res_id).display_name

    """ Validation to approving request
    """
    def _validate_approving(self):
        
        listed_as_approver = any(self.mapped(lambda r:self.env.user.id in r.approver_ids.ids))
        if not listed_as_approver:
            raise UserError(_("You Can't Approve This Document!\nThis Warning will be reported to administrator!"))

        # make sure not in rejected list
        all_has_rejected_by_user = all(self.mapped(lambda r:self.env.user.id in r.rejected_by_ids.ids))
        if all_has_rejected_by_user:
            raise UserError(_("You has been rejected this document!"))
        
        # make sure on same document, less level has been approved
        # find same
        to_approve_rules = self.filtered(lambda r:self.env.user.id in r.approver_ids.ids and self.env.user.id not in r.rejected_by_ids.ids and self.env.user.id not in r.approved_by_ids.ids)
        for appr in to_approve_rules:
            approvals = self.search([('matrix_id','=',appr.matrix_id.id), ('approver_seq','<',appr.approver_seq), ('res_model_id','=',appr.res_model_id.id), ('res_id','=',appr.res_id)])
             # approvals = to_approve_rules.mapped()
            if len(approvals):
                if not all(approvals.mapped(lambda r:r.approved)):
                    raise UserError(_("Cant approving until document has been approved by %s!") % _(approvals.mapped('approver_ids').mapped('name')))


    def approve(self):
        self._validate_approving()
        
        self.write({
            'approved_by_ids':[(4,self.env.user.id)],
        })

    def _validate_reject(self):
        if self.env.user.id not in self.approver_ids.ids:
            raise UserError(_("You Can't Reject This Document!\nThis Warning will be reported to administrator!"))

        if self.env.user.id in self.approved_by_ids.ids:
            raise UserError(_("You has been approved this document!"))

    def reject(self):
        self._validate_reject()
        self.write({
            'rejected_by_ids':[(4,self.env.user.id)],
        })

    @api.depends('approver_ids','approved_by_ids', 'rejected_by_ids')
    def _compute_approval(self):
        def is_approved(approved_len, minimum):
            res = False
            
            if approved_len >= minimum:
                res = True
            return res
        
        for rec in self:
            
            approved_count = len(rec.approved_by_ids)
            rejected_count = len(rec.rejected_by_ids)
            res = {
                'approved_count': approved_count,
                'rejected_count': rejected_count,
                'approved': is_approved(approved_count, rec.minimum_approved)
            }
            rec.update(res)

class ResUsers(models.Model):
    _inherit = 'res.users'

    doc_approval_ids = fields.Many2many('approval.matrix.document.approval', compute="_compute_doc_approval_ids")

    def _compute_doc_approval_ids(self):
        
        q = """SELECT approval_id,user_id FROM approval_matrix_doc_approval_user_rel WHERE user_id in %s"""
        self.env.cr.execute(q, (tuple(self.ids),))
        res = self.env.cr.fetchall()
        
        mapped_data = {}
        if len(res):
            for row in res:
                v = row[0]
                k = row[1]
                curr = mapped_data.get(k)
                if curr:
                    mapped_data.update({k:curr+[v]})
                else:
                    mapped_data.update({k:[v]})
        
        Doc = self.env['approval.matrix.document.approval']
        
        for rec in self:
            res = Doc
            has_map_data = mapped_data.get(rec.id)
            if has_map_data:
                res = Doc.sudo().browse(has_map_data)
            rec.doc_approval_ids = res

    def doc_as_approver(self, model=None):
        self.ensure_one()
        
        if model==None:
            active_model = self._context('active_model')
            if active_model:
                model = active_model
        
        res = self.doc_approval_ids.filtered(lambda r:r.res_model==model).mapped('res_id')
        return res

class RejectionMessages(models.Model):
    _name = 'rejection.message'
    _description = 'Rejection Message'

    
    res_model_id = fields.Many2one('ir.model', 'Document Model', index=True, ondelete='cascade', required=False)
    res_model = fields.Char('Related Document Model', index=True, related='res_model_id.model', compute_sudo=True, store=True, readonly=True)

    name = fields.Char(string="Reason", required=True)
    active = fields.Boolean(string="Active", default=True)



class MessagePostWizard(models.TransientModel):
    _name = 'message.post.wizard'
    _description = "message.post.wizard"

    prefix_message = fields.Char("Prefix Message")
    messages = fields.Text(required=False)
    suffix_action = fields.Char()
    rejection_message_id = fields.Many2one('rejection.message', string="Rejection Message")
    rejection_message_string = fields.Char(related="rejection_message_id.name", readonly=True)


    def confirm(self):
        res_id = self._context.get('active_id')
        model = self._context.get('active_model')
        if not res_id or not model:
            raise UserError("Require to get context active id and active model!")
        
        if not self.rejection_message_id.id and not self.messages:
            raise ValidationError(_("Please Fill Message or Choose From Selection!"))
        
        Env = self.env[model]
        Record = Env.sudo().browse(res_id)

        if len(Record):
            
            # msgs = "%s%s" % (self.prefix_message+"<br/>" if self.prefix_message else "", self.messages)
            msgs = []
            if self.prefix_message:
                msgs.append("<h5>"+self.prefix_message+"</h5>")


            if self.rejection_message_id.id:
                msgs.append("<span class=\"text-danger\">%s</span>" % (self.rejection_message_string,))
            
            if self.messages:
                msgs.append(self.messages)

            msgs = "<br/>".join(msgs)
            
            
            Record.message_post(body=msgs)
            if len(self.suffix_action):
                getattr(Record, self.suffix_action)()