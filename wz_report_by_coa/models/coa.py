# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime

class WzAccount(models.Model):
	_inherit = 'account.account'

	ycogs = fields.Boolean(string="YCOGS", default=False)
	ypnl = fields.Boolean(string="YPNL", default=False)
	ybs = fields.Boolean(string="YBS", default=False)
	mcogs = fields.Boolean(string="MCOGS", default=False)
	mpnl = fields.Boolean(string="MPNL", default=False)
	mbs = fields.Boolean(string="MBS", default=False)
	cogsvslmly = fields.Boolean(string="COGS VS LM LY", default=False)
	pnlvslmly = fields.Boolean(string="PNL VS LM LY", default=False)
	bslvslmly = fields.Boolean(string="BS VS LM LY", default=False)
	cogsytd = fields.Boolean(string="COGS YTD", default=False)
	pnlytd = fields.Boolean(string="PNL YTD", default=False)
	bsytd = fields.Boolean(string="BS YTD", default=False)


class StockMove(models.Model):
	_inherit = "stock.move"

	product_id = fields.Many2one(
		domain="[('type', 'in', ['product', 'consu', 'service']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]"
	)


	@api.depends('raw_material_production_id.qty_producing', 'product_uom_qty', 'product_uom')
	def _compute_should_consume_qty(self):
		# 1. Jalankan dulu kalkulasi bawaan Odoo untuk semua komponen (seperti Bahan Baku)
		super(StockMove, self)._compute_should_consume_qty()
		
		# 2. Timpa/Override khusus untuk komponen bertipe 'service'
		for move in self:
			if move.raw_material_production_id and move.product_id.type == 'service':
				move.should_consume_qty = 1.0  # Dipaksa selalu 1.00 di tampilan UI

	def _get_src_account(self, account_data):
		res = super(StockMove, self)._get_src_account(account_data)
		# TAMBAHKAN 'and self.raw_material_production_id'
		if self.product_id.type == 'service' and self.raw_material_production_id:
			expense_account = (
				self.product_id.property_account_expense_id 
				or self.product_id.categ_id.property_account_expense_categ_id
			)
			if expense_account:
				return expense_account.id
		return res

	def _price_unit(self):
		self.ensure_one()
		# Jika produk bertipe service dan merupakan komponen MO
		if self.product_id.type == 'service' and self.raw_material_production_id:
			print("_price_unit")
			if hasattr(self, 'cost') and self.cost:
				# Mengembalikan unit cost (cost / quantity jika cost di MO mewakili TOTAL upah)
				qty = self.product_uom_qty or 1.0
				return self.cost / qty
			elif self.price_unit:
				return self.price_unit

	def _get_price_unit(self):
		self.ensure_one()
		# Jika produk tipe service dan berasal dari komponen MO
		if self.product_id.type == 'service' and self.raw_material_production_id:
			print("_get_price_unit")
			# Gunakan field custom 'cost' atau 'price_unit' yang diisi dari MO
			# Jika field custom Anda bernama 'cost' dan mewakili total/unit cost:
			if hasattr(self, 'cost') and self.cost:
				return self.cost
			elif self.price_unit:
				return self.price_unit

		return super(StockMove, self)._get_price_unit()

	# def _get_price_unit(self):
	# 	self.ensure_one()
	# 	if self.product_id.type == 'service' and self.raw_material_production_id:
	# 		return self.product_id.standard_price
	# 	return super(StockMove, self)._get_price_unit()

	# def _get_price_unit(self):
	# 	self.ensure_one()
	# 	if self.product_id.type == 'service':
	# 		return self.product_id.standard_price
	# 	return super(StockMove, self)._get_price_unit()

	# def _create_out_svl(self, forced_quantity=None):
	# 	print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	# 	svl_moves = super(StockMove, self)._create_out_svl(forced_quantity=forced_quantity)
	# 	print("bbbbbbbbbbbbbbbbbbbbbbbbbbbb")
		
	# 	service_moves = self.filtered(
	# 		lambda m: m.raw_material_production_id 
	# 		and m.product_id.type == 'service' 
	# 		and not m.stock_valuation_layer_ids
	# 	)
	# 	print("service_moves",service_moves)
	# 	for move in service_moves:
	# 		quantity = forced_quantity or move.product_uom_qty
	# 		# unit_cost = move.product_id.standard_price
	# 		unit_cost = move.cost
	# 		print("unit_cost",unit_cost)
	# 		self.env['stock.valuation.layer'].create({
	# 			'company_id': move.company_id.id,
	# 			'product_id': move.product_id.id,
	# 			'quantity': -quantity,
	# 			'unit_cost': unit_cost,
	# 			'value': -quantity * unit_cost,
	# 			'remaining_qty': 0,
	# 			'stock_move_id': move.id,
	# 			'description': move.reference or move.origin,
	# 		})
	# 		# Catatan: Pemanggilan _validate_accounting_entries() DIHAPUS dari sini
	# 		# karena Odoo akan memanggilnya secara otomatis di alur _action_done()
			
	# 	return svl_moves



	def _create_out_svl(self, forced_quantity=None):
		# 1. Jalankan dulu fungsi standar Odoo
		svl_ids = super(StockMove, self)._create_out_svl(forced_quantity=forced_quantity)

		# 2. Cari move service/tenaga kerja yang merupakan komponen MO
		service_moves = self.filtered(
			lambda m: m.product_id.type == 'service' and m.raw_material_production_id
		)

		for move in service_moves:
			print("_create_out_svl")
			# Ambil nilai cost dari field 'cost' pada stock.move tersebut
			unit_cost = move.cost if hasattr(move, 'cost') and move.cost else move.price_unit

			# Cari SVL yang baru saja dibuat untuk move ini
			move_svls = self.env['stock.valuation.layer'].search([('stock_move_id', '=', move.id)])
			
			if move_svls:
				print("move_svls")
				for svl in move_svls:
					qty = abs(svl.quantity)
					new_value = -1 * (qty * unit_cost)
					# Force update nilai unit_cost dan total value di SVL
					svl.write({
						'unit_cost': unit_cost,
						'value': new_value,
					})
			else:
				print("noooooo move_svls")
				# Jika Odoo tidak otomatis membuat SVL (karena tipe produk service), buat manual SVL-nya
				quantity = forced_quantity or move.product_uom_qty
				self.env['stock.valuation.layer'].create({
					'company_id': move.company_id.id,
					'product_id': move.product_id.id,
					'quantity': -quantity,
					'unit_cost': unit_cost,
					'value': -quantity * unit_cost,
					'remaining_qty': 0,
					'stock_move_id': move.id,
					'description': move.reference or move.origin,
				})

		return svl_ids

	def _account_entry_move(self, qty, description, svl_id, cost):
		if self.product_id.type == 'service' and self.raw_material_production_id:
			am_vals = []
			if self._should_exclude_for_valuation():
				return am_vals

			company_from = self._is_out() and self.mapped('move_line_ids.location_id.company_id') or False
			journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation()

			# Ambil akun Expense (untuk posisi Kredit)
			expense_account_id = self._get_src_account({
				'stock_input': self.env['account.account'].browse(acc_src),
				'stock_output': self.env['account.account'].browse(acc_dest),
				'stock_valuation': self.env['account.account'].browse(acc_valuation),
			})

			if self._is_out():
				# HAPUS: cost = -1 * cost (Jangan dikali -1 agar posisi Debit/Kredit tidak terbalik otomatis)
				am_vals.append(self.with_company(company_from)._prepare_account_move_vals(
					acc_dest, expense_account_id, journal_id, qty, description, svl_id, cost
				))
			return am_vals

		return super(StockMove, self)._account_entry_move(qty, description, svl_id, cost)


class MrpProduction(models.Model):
	_inherit = 'mrp.production'

	def _get_moves_raw_values(self):
		print("_get_moves_raw_values")
		moves = []
		for production in self:
			if not production.bom_id:
				continue
			factor = production.product_uom_id._compute_quantity(
				production.product_qty, production.bom_id.product_uom_id
			) / production.bom_id.product_qty
			
			boms, lines = production.bom_id.explode(
				production.product_id, 
				factor, 
				picking_type=production.bom_id.picking_type_id
			)
			
			for bom_line, line_data in lines:
				if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom' or \
						bom_line.product_id.type not in ['product', 'consu', 'service']:
					continue
				
				operation = bom_line.operation_id.id or (
					line_data['parent_line'] and line_data['parent_line'].operation_id.id
				)
				
				moves.append(production._get_move_raw_values(
					bom_line.product_id,
					line_data['qty'] if bom_line.product_id.type != 'service' else 1,
					bom_line.product_uom_id,
					operation,
					bom_line
				))
		return moves

	# def _update_raw_moves(self, factor):
	# 	res = super(MrpProduction, self)._update_raw_moves(factor)
	# 	# Reset ulang kuantitas khusus komponen service agar tetap 1
	# 	service_moves = self.move_raw_ids.filtered(
	# 		lambda m: m.product_id.type == 'service' and m.state not in ('done', 'cancel')
	# 	)
	# 	if service_moves:
	# 		service_moves.write({'product_uom_qty': 1.0})
	# 	return res

	def _set_qty_producing(self):
		print("_set_qty_producing")
		if self.product_id.tracking == 'serial':
			qty_producing_uom = self.product_uom_id._compute_quantity(self.qty_producing, self.product_id.uom_id, rounding_method='HALF-UP')
			if qty_producing_uom != 1:
				self.qty_producing = self.product_id.uom_id._compute_quantity(1, self.product_uom_id, rounding_method='HALF-UP')

		for move in (self.move_raw_ids.filtered(lambda m: m.product_id.type != 'service') | self.move_finished_ids.filtered(lambda m: m.product_id != self.product_id and m.product_id.type != 'service')):
			if move._should_bypass_set_qty_producing() or not move.product_uom:
				continue

			new_qty = float_round((self.qty_producing - self.qty_produced) * move.unit_factor, precision_rounding=move.product_uom.rounding)
			if self.use_auto_consume_components_lots and move.has_tracking in ('lot', 'serial'):
				if float_compare(move.reserved_availability, 0, precision_rounding=move.product_uom.rounding) <= 0:
					continue
				else:
					new_qty = min(new_qty, move.reserved_availability)

			move.move_line_ids.filtered(lambda ml: ml.state not in ('done', 'cancel')).qty_done = 0
			move._set_quantity_done(new_qty)