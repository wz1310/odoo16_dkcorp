# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
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

	# Mengubah ke Many2many agar 1 MO bisa memilih banyak Sales Order
	sale_order_ids = fields.Many2many('sale.order', string='Sales Order Ref')
	max_worker_qty = fields.Integer(string='Maksimal Pekerja', compute='_compute_max_worker_qty', store=True)
	worker_line_ids = fields.One2many('mrp.production.worker.line', 'production_id', string='Daftar Pekerja')



	@api.onchange('move_raw_ids')
	def _onchange_move_raw_ids(self):
		print("ssssssssssssssssss")
		for x in self.move_raw_ids:
			if x.product_id.type == 'service' and x.product_id.engine_load:
				print("waaaaaaaaaaaaaaa")
				percent = x.product_id.engine_percent/100 if x.product_id.engine_percent > 0 else 0 
				total_other_cost = percent * (sum([(line.rill_cost if line.rill_cost else line.cost)for line in self.move_raw_ids if line != x]))
				x.cost = total_other_cost


	@api.depends('sale_order_ids', 'sale_order_ids.order_line.product_uom_qty')
	def _compute_max_worker_qty(self):
		formula = self.env['mrp.worker.formula'].search([], limit=1)
		for mo in self:
			if mo.sale_order_ids and formula and formula.qty_base > 0:
				# Menjumlahkan product_uom_qty dari seluruh SO yang dipilih
				total_so_qty = sum(mo.sale_order_ids.mapped('order_line.product_uom_qty'))
				multiplier = math.ceil(total_so_qty / formula.qty_base)
				mo.max_worker_qty = multiplier * formula.worker_count
			else:
				mo.max_worker_qty = 0

	# @api.onchange('sale_order_id')
	# def _onchange_sale_order_id(self):
	#     if self.sale_order_id:
	#         # Menggunakan order_line (bukan order_lines)
	#         total_so_qty = sum(self.sale_order_id.order_line.mapped('product_uom_qty'))
	#         service_moves = self.move_raw_ids.filtered(lambda m: m.product_id.type == 'service')
	#         for move in service_moves:
	#             move.product_uom_qty = total_so_qty

	@api.constrains('worker_line_ids', 'max_worker_qty')
	def _check_max_worker_qty(self):
		for mo in self:
			if mo.sale_order_ids and len(mo.worker_line_ids) > mo.max_worker_qty:
				raise ValidationError(
					_("Jumlah pekerja yang diinput (%s) melebihi batas maksimal (%s) berdasarkan formula SO!") 
					% (len(mo.worker_line_ids), mo.max_worker_qty)
				)

	@api.onchange('worker_line_ids')
	def _onchange_worker_id(self):
		total_so_qty = sum(self.sale_order_ids.mapped('order_line.product_uom_qty'))
		service_moves = self.move_raw_ids.filtered(
			lambda m: m.product_id.type == 'service' and m.product_id.worker
			)
		for move in service_moves:
			# move.product_id.standard_price = sum([x.wage for x in self.worker_line_ids])
			move.cost = (sum([x.wage for x in self.worker_line_ids]) / total_so_qty) * self.qty_producing if total_so_qty else 0.0

	# def write(self, vals):
	#     res = super(MrpProduction, self).write(vals)
	#     if 'worker_line_ids' in vals:
	#         for mo in self:
	#             total_wage = sum(mo.worker_line_ids.mapped('wage'))
	#             service_moves = mo.move_raw_ids.filtered(lambda m: m.product_id.type == 'service')
	#             for move in service_moves:
	#                 # Update ke master produk atau ke unit price komponen
	#                 # move.product_id.standard_price = total_wage
	#                 move.cost = total_wage
	#     return res


	def write(self, vals):
		res = super(MrpProduction, self).write(vals)
		# Jalankan logika jika worker_line_ids diubah ATAU jika MO baru saja di-confirm/di-write
		for mo in self:
			total_so_qty = sum(mo.sale_order_ids.mapped('order_line.product_uom_qty'))
			total_wage = (sum(mo.worker_line_ids.mapped('wage')) / total_so_qty) * mo.qty_producing if total_so_qty else 0.0
			service_moves = mo.move_raw_ids.filtered(lambda m: m.product_id.type == 'service' and m.product_id.worker)
			
			if service_moves:
				# Memaksa update price_unit pada stock move
				# service_moves.sudo().write({'price_unit': total_wage})
				service_moves.sudo().write({'cost': total_wage})
				
				# Jika Anda MEMANG ingin mengubah Cost di Master Produk juga:
				# for move in service_moves:
				#     move.product_id.sudo().write({'standard_price': total_wage})
		return res

	def action_confirm(self):
		res = super(MrpProduction, self).action_confirm()
		for mo in self:
			total_so_qty = sum(mo.sale_order_ids.mapped('order_line.product_uom_qty'))
			total_wage = (sum(mo.worker_line_ids.mapped('wage')) / total_so_qty) * mo.qty_producing if total_so_qty else 0.0
			service_moves = mo.move_raw_ids.filtered(lambda m: m.product_id.type == 'service' and m.product_id.worker)
			if service_moves:
				service_moves.sudo().write({'cost': total_wage})
		return res


class MrpProduct(models.Model):
	_inherit = 'product.product'

	worker = fields.Boolean(string='Worker', default=False)
	engine_load = fields.Boolean(string='Engine Load', default=False)
	engine_percent = fields.Integer(string='Percentage', default=False)