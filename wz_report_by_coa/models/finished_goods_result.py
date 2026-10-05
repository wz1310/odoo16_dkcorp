from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductCategory(models.Model):
	_inherit = 'product.category'

	is_finish_good = fields.Boolean(string='Finish Good')

class FinishedGoodsResult(models.Model):
	_name = 'finished.goods.result'
	_description = 'Finished Goods Result'
	_order = 'id desc'

	name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
	date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
	product_id = fields.Many2one('product.product', string='Product', required=True)
	qty_result = fields.Float(string='Qty Result', required=True, default=0.0)
	state = fields.Selection([
		('draft', 'Draft'),
		('done', 'Done'),
		('cancel', 'Cancelled')
	], string='Status', default='draft', required=True, tracking=True)
	
	production_id = fields.Many2one('mrp.production', string='Manufacturing Order', ondelete='cascade')

	@api.constrains('qty_result', 'product_id')
	def _check_qty_result_serial(self):
		for record in self:
			if record.product_id and record.product_id.tracking == 'serial':
				if record.qty_result > 1.0:
					raise UserError(_('Produk %s menggunakan tracking Serial Number, sehingga Qty Result tidak boleh lebih dari 1.0!') % record.product_id.display_name)

	@api.onchange('product_id', 'qty_result')
	def _onchange_qty_result_serial(self):
		if self.product_id and self.product_id.tracking == 'serial' and self.qty_result > 1.0:
			self.qty_result = 1.0
			return {
				'warning': {
					'title': _('Peringatan Serial Number'),
					'message': _('Produk ini melacak Unique Serial Number, kuantitas otomatis disesuaikan menjadi 1.')
				}
			}

	@api.model
	def create(self, vals):
		if vals.get('name', _('New')) == _('New'):
			vals['name'] = self.env['ir.sequence'].next_by_code('finished.goods.result') or _('New')
		return super(FinishedGoodsResult, self).create(vals)

	def action_validate(self):
		self._check_qty_result_serial()
		self.write({'state': 'done'})

	def action_cancel(self):
		self.write({'state': 'cancel'})

	def action_draft(self):
		self.write({'state': 'draft'})

	def action_sync_qty_to_mo(self):
		for record in self:
			if record.production_id:
				if record.product_id.tracking == 'serial' and record.qty_result > 1.0:
					raise UserError(_('Tidak dapat sinkronisasi: Produk %s berjenis Serial Number (Qty max 1).') % record.product_id.display_name)
				if record.state != 'done':
					raise UserError(_('Silahkan validasi terlebih dahulu . . .'))
				record.production_id.qty_producing = record.qty_result

	def action_view_mo(self):
		self.ensure_one()
		return {
			'name': _('Manufacturing Order'),
			'type': 'ir.actions.act_window',
			'res_model': 'mrp.production',
			'view_mode': 'form',
			'res_id': self.production_id.id,
		}


class MrpProduction(models.Model):
	_inherit = 'mrp.production'

	fgr_ids = fields.One2many('finished.goods.result', 'production_id', string='Finished Goods Results')
	fgr_count = fields.Integer(string='FGR Count', compute='_compute_fgr_count')

	@api.depends('fgr_ids')
	def _compute_fgr_count(self):
		for record in self:
			record.fgr_count = len(record.fgr_ids)

	def action_create_fgr(self):
		self.ensure_one()
		
		# Validasi kuantitas jika tracking berupa Unique Serial Number
		if self.product_id.categ_id.is_finish_good == False:
			raise UserError(_('Produk bukan finish good'))
		initial_qty = self.qty_producing or self.product_qty
		if self.product_id.tracking == 'serial' and initial_qty > 1.0:
			initial_qty = 1.0

		fgr_val = {
			'production_id': self.id,
			'product_id': self.product_id.id,
			'qty_result': initial_qty,
			'date': self.date_planned_start and self.date_planned_start.date() or fields.Date.today(),
		}
		fgr = self.env['finished.goods.result'].create(fgr_val)
		return {
			'name': _('Finished Goods Result'),
			'type': 'ir.actions.act_window',
			'res_model': 'finished.goods.result',
			'view_mode': 'form',
			'res_id': fgr.id,
		}

	def action_sync_from_fgr(self):
		self.ensure_one()
		fgr = self.fgr_ids.filtered(lambda r: r.state == 'done')[:1]
		if not fgr:
			raise UserError(_('Tidak ada data FGR yang valid/aktif untuk melakukan sinkronisasi.'))
		
		if self.product_id.tracking == 'serial' and fgr.qty_result > 1.0:
			raise UserError(_('Produk %s ditolak sinkronisasi karena menggunakan tracking Serial Number (Qty tidak boleh lebih dari 1).') % self.product_id.display_name)
			
		self.qty_producing = fgr.qty_result

	def action_view_fgr(self):
		self.ensure_one()
		action = self.env["ir.actions.actions"]._for_xml_id("wz_report_by_coa.action_finished_goods_result")
		if self.fgr_count == 1:
			action['views'] = [(self.env.ref('wz_report_by_coa.view_finished_goods_result_form').id, 'form')]
			action['res_id'] = self.fgr_ids.id
		else:
			action['domain'] = [('id', 'in', self.fgr_ids.ids)]
		return action