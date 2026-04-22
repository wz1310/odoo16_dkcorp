# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class MrpApproveInherit(models.Model):
    _name = 'mrp.production' # Definisikan kembali model target
    # Gabungkan inherit menjadi satu list
    _inherit = ["mrp.production", "approval.matrix.mixin"]

    
    @api.depends('approval_ids.approved')
    def _compute_approved(self):
        for rec in self:
            if not rec.approval_ids:
                rec.approved = False
            else:
                # Mengambil status approved dari tiap baris di tabel approval
                rec.approved = all(rec.approval_ids.mapped('approved'))

    def button_done_mark(self):
        print("aaaaaaaaaaaaaaaaaaaa")
        self.ensure_one()
        model = self._get_model()
        matrix = self.env['approval.matrix'].with_context(self._context.copy()).find_possible_matrix(self.company_id, model, self)

        if len(matrix):
            if self.approved != True:
                raise ValidationError(_("Butuh Approval"))
        return super(MrpApproveInherit, self).button_done_mark()

    # def cek_matrix(self):
    #     self.ensure_one()
    #     model = self._get_model()
    #     matrix = self.env['approval.matrix'].with_context(self._context.copy()).find_possible_matrix(self.company_id, model, self)
    #     if len(matrix):
    #         matrix.generate_approval_docs(model, self)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(MrpApproveInherit, self).create(vals_list)
        print("ccccccccccccccc")
        model = self._get_model()
        companies = records.company_id
        matrix = self.env['approval.matrix']\
        .with_context(self._context.copy())\
        .find_possible_matrix(companies, model, records)
        if matrix:
            matrix.generate_approval_docs(model, records)
            records.approval_ids._send_notification()
        return records