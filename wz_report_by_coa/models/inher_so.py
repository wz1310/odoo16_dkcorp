# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.exceptions import ValidationError


class SaleOrderWorkerLine(models.Model):
    _name = 'sale.order.worker.line'
    _description = 'Detail Pekerja Sales Order'

    order_id = fields.Many2one('sale.order', string='Sales Order', ondelete='cascade')
    worker_id = fields.Many2one('mrp.worker', string='Pekerja', required=True)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    worker_line_ids = fields.One2many(
        'sale.order.worker.line', 
        'order_id', 
        string='Daftar Pekerja'
    )
    batch_id = fields.Many2one('sale.order.batch', string='Batch')


class SaleOrderBatchWorkerLine(models.Model):
    _name = 'sale.order.batch.worker.line'
    _description = 'Detail Pekerja Master Batch'
    _rec_name = 'worker_id'

    batch_id = fields.Many2one('sale.order.batch', string='Batch', ondelete='cascade')
    worker_id = fields.Many2one('mrp.worker', string='Pekerja', required=True)


class SaleOrderBatch(models.Model):
    _name = 'sale.order.batch'
    _description = 'Master Batch Sales Order'

    name = fields.Char(string='Nama Batch', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Field One2many untuk merekam Sales Order yang terhubung ke Batch ini
    sale_order_ids = fields.One2many(
        'sale.order', 
        'batch_id', 
        string='Sales Order'
    )
    # Field One2many untuk merekam Daftar Pekerja (mrp.worker) pada Batch ini
    worker_line_ids = fields.One2many(
        'sale.order.batch.worker.line',
        'batch_id',
        string='Daftar Pekerja'
    )


# =========================================================================
# WIZARD / POPUP UNTUK ACTION 'SET DAFTAR PEKERJA & BATCH'
# =========================================================================

class SaleOrderAssignWorkerWizardLine(models.TransientModel):
    _name = 'sale.order.assign.worker.wizard.line'
    _description = 'Detail Pekerja Wizard Batch'

    wizard_id = fields.Many2one('sale.order.assign.worker.wizard', string='Wizard', ondelete='cascade')
    worker_id = fields.Many2one('mrp.worker', string='Pekerja', required=True)


class SaleOrderAssignWorkerWizard(models.TransientModel):
    _name = 'sale.order.assign.worker.wizard'
    _description = 'Wizard Set Pekerja dan Batch Sales Order'

    batch_id = fields.Many2one(
        'sale.order.batch', 
        string='Batch',
        help="Pilih Batch yang sudah ada atau buat baru secara langsung."
    )
    max_worker_qty = fields.Integer(
        string='Maksimal Pekerja', 
        compute='_compute_max_worker_qty'
    )
    worker_line_ids = fields.One2many(
        'sale.order.assign.worker.wizard.line', 
        'wizard_id', 
        string='Daftar Pekerja'
    )

    @api.depends('worker_line_ids')
    def _compute_max_worker_qty(self):
        active_ids = self.env.context.get('active_ids', [])
        orders = self.env['sale.order'].browse(active_ids)
        formula = self.env['mrp.worker.formula'].search([], limit=1)

        for wizard in self:
            if orders and formula and formula.qty_base > 0:
                total_so_qty = sum(orders.mapped('order_line.product_uom_qty'))
                multiplier = math.ceil(total_so_qty / formula.qty_base)
                wizard.max_worker_qty = multiplier * formula.worker_count
            else:
                wizard.max_worker_qty = 0

    @api.constrains('worker_line_ids', 'max_worker_qty')
    def _check_max_worker_qty(self):
        for wizard in self:
            if wizard.max_worker_qty > 0 and len(wizard.worker_line_ids) > wizard.max_worker_qty:
                raise ValidationError(
                    _("Jumlah pekerja yang diinput (%s) melebihi batas maksimal (%s) berdasarkan formula SO!") 
                    % (len(wizard.worker_line_ids), wizard.max_worker_qty)
                )

    def action_apply(self):
        self.ensure_one()
        active_ids = self.env.context.get('active_ids', [])
        orders = self.env['sale.order'].browse(active_ids)

        if not orders:
            raise ValidationError(_("Tidak ada Sales Order yang dipilih!"))

        # Validasi ulang sebelum menyimpan
        if self.max_worker_qty > 0 and len(self.worker_line_ids) > self.max_worker_qty:
            raise ValidationError(
                _("Jumlah pekerja yang diinput (%s) melebihi batas maksimal (%s) berdasarkan formula SO!") 
                % (len(self.worker_line_ids), self.max_worker_qty)
            )

        # Siapkan tuple pembuatan record 'sale.order.worker.line'
        worker_vals = [(0, 0, {'worker_id': line.worker_id.id}) for line in self.worker_line_ids]

        # Update Sales Order yang diproses
        for order in orders:
            vals = {}
            if self.batch_id:
                vals['batch_id'] = self.batch_id.id

            if worker_vals:
                # Menghapus list pekerja lama lalu mengganti dengan yang baru dari popup
                vals['worker_line_ids'] = [(5, 0, 0)] + worker_vals

            if vals:
                order.write(vals)

        # Update Daftar Pekerja (mrp.worker) pada Master Batch
        if self.batch_id and worker_vals:
            batch_worker_vals = [(0, 0, {'worker_id': line.worker_id.id}) for line in self.worker_line_ids]
            self.batch_id.write({
                'worker_line_ids': [(5, 0, 0)] + batch_worker_vals
            })

        return {'type': 'ir.actions.act_window_close'}