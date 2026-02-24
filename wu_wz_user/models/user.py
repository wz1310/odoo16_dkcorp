# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockPickingInherit(models.Model):
    _name = 'stock.picking' # Definisikan kembali model target
    # Gabungkan inherit menjadi satu list
    _inherit = ["stock.picking", "approval.matrix.mixin"]

    # Override fungsi compute agar tidak bernilai True saat tabel kosong
    @api.depends('approval_ids.approved')
    def _compute_approved(self):
        for rec in self:
            if not rec.approval_ids:
                rec.approved = False
            else:
                # Mengambil status approved dari tiap baris di tabel approval
                rec.approved = all(rec.approval_ids.mapped('approved'))

    def button_validate(self):
        find_matrix = self.env['approval.matrix'].search([('res_model','=',self._name)]).active
        print("find mat",find_matrix)
        if self.approved != True and find_matrix == True:
            raise ValidationError(_("Butuh Approval"))
        return super(StockPickingInherit, self).button_validate()