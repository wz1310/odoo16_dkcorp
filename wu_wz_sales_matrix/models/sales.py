# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class SaleApproveInherit(models.Model):
    _name = 'sale.order' # Definisikan kembali model target
    # Gabungkan inherit menjadi satu list
    _inherit = ["sale.order", "approval.matrix.mixin"]

    
    @api.depends('approval_ids.approved')
    def _compute_approved(self):
        for rec in self:
            if not rec.approval_ids:
                rec.approved = False
            else:
                # Mengambil status approved dari tiap baris di tabel approval
                rec.approved = all(rec.approval_ids.mapped('approved'))

    def action_confirm_inherit(self):
        self.ensure_one()
        model = self._get_model()
        matrix = self.env['approval.matrix'].with_context(self._context.copy()).find_possible_matrix(self.company_id, model, self)

        if len(matrix):
            if self.approved != True:
                raise ValidationError(_("Butuh Approval"))
        return super(SaleApproveInherit, self).action_confirm_inherit()

    def cek_matrix(self):
        self.ensure_one()
        model = self._get_model()
        matrix = self.env['approval.matrix'].with_context(self._context.copy()).find_possible_matrix(self.company_id, model, self)
        if len(matrix):
            matrix.generate_approval_docs(model, self)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SaleApproveInherit, self).create(vals_list)
        model = self._get_model()
        companies = records.company_id
        matrix = self.env['approval.matrix']\
        .with_context(self._context.copy())\
        .find_possible_matrix(companies, model, records)
        if matrix:
            matrix.generate_approval_docs(model, records)
            records.approval_ids._send_notification()
        return records