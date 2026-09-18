# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MrpWorker(models.Model):
    _name = 'mrp.worker'
    _description = 'Master Pekerja MRP'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='Pekerja', required=True)
    wage = fields.Float(string='Upah', required=True, default=0.0)
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True, 
        default=lambda self: self.env.company
    )


class MrpWorkerFormula(models.Model):
    _name = 'mrp.worker.formula'
    _description = 'Master Formula Pekerja SO'

    name = fields.Char(string='Deskripsi', compute='_compute_name', store=True)
    qty_base = fields.Float(string='QTY', required=True, default=1.0)
    worker_count = fields.Integer(string='Jumlah Pekerja', required=True, default=1)

    @api.depends('qty_base', 'worker_count')
    def _compute_name(self):
        for record in self:
            record.name = f"QTY Base {record.qty_base} -> {record.worker_count} Pekerja"


class MrpProductionWorkerLine(models.Model):
    _name = 'mrp.production.worker.line'
    _description = 'Detail Pekerja Manufacturing Order'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', ondelete='cascade')
    worker_id = fields.Many2one('mrp.worker', string='Pekerja', required=True)
    wage = fields.Float(string='Upah', related='worker_id.wage', readonly=True)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    sale_order_id = fields.Many2one('sale.order', string='Sales Order Ref')
    max_worker_qty = fields.Integer(string='Maksimal Pekerja', compute='_compute_max_worker_qty', store=True)
    worker_line_ids = fields.One2many('mrp.production.worker.line', 'production_id', string='Daftar Pekerja')

    @api.depends('sale_order_id', 'sale_order_id.order_line.product_uom_qty')
    def _compute_max_worker_qty(self):
        formula = self.env['mrp.worker.formula'].search([], limit=1)
        for mo in self:
            if mo.sale_order_id and formula and formula.qty_base > 0:
                # Menggunakan order_line (bukan order_lines)
                total_so_qty = sum(mo.sale_order_id.order_line.mapped('product_uom_qty'))
                multiplier = math.ceil(total_so_qty / formula.qty_base)
                mo.max_worker_qty = multiplier * formula.worker_count
            else:
                mo.max_worker_qty = 0

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            # Menggunakan order_line (bukan order_lines)
            total_so_qty = sum(self.sale_order_id.order_line.mapped('product_uom_qty'))
            service_moves = self.move_raw_ids.filtered(lambda m: m.product_id.type == 'service')
            for move in service_moves:
                move.product_uom_qty = total_so_qty

    @api.constrains('worker_line_ids', 'max_worker_qty')
    def _check_max_worker_qty(self):
        for mo in self:
            if mo.sale_order_id and len(mo.worker_line_ids) > mo.max_worker_qty:
                raise ValidationError(
                    _("Jumlah pekerja yang diinput (%s) melebihi batas maksimal (%s) berdasarkan formula SO!") 
                    % (len(mo.worker_line_ids), mo.max_worker_qty)
                )

    @api.onchange('worker_line_ids')
    def _onchange_worker_id(self):
        service_moves = self.move_raw_ids.filtered(
            lambda m: m.product_id.type == 'service'
            )
        for move in service_moves:
            move.product_id.standard_price = sum([x.wage for x in self.worker_line_ids])