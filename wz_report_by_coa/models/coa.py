# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

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

	def _get_price_unit(self):
		self.ensure_one()
		if self.product_id.type == 'service' and self.raw_material_production_id:
			return self.product_id.standard_price
		return super(StockMove, self)._get_price_unit()

	def _create_out_svl(self, forced_quantity=None):
		svl_moves = super(StockMove, self)._create_out_svl(forced_quantity=forced_quantity)
		
		service_moves = self.filtered(
			lambda m: m.raw_material_production_id 
			and m.product_id.type == 'service' 
			and not m.stock_valuation_layer_ids
		)
		
		for move in service_moves:
			quantity = forced_quantity or move.product_uom_qty
			unit_cost = move.product_id.standard_price
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
			# Catatan: Pemanggilan _validate_accounting_entries() DIHAPUS dari sini
			# karena Odoo akan memanggilnya secara otomatis di alur _action_done()
			
		return svl_moves

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
					line_data['qty'],
					bom_line.product_uom_id,
					operation,
					bom_line
				))
		return moves