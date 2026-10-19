# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_round

import logging
_logger = logging.getLogger(__name__)

class SalesInherit(models.Model):
	_inherit = 'sale.order'
	
	send_by = fields.Selection(
		[('grab', 'Grab'),
		 ('gojek', 'Gojek'),
		 ('lala_move', 'Lala Move'),
		 ('si_cepat', 'Sicepat'),
		 ('jnt', 'JNT'),
		 ('jne', 'JNE'),
		 ('lainnya', 'Lainnya'),
		 ],
		string='Opsi Pengiriman')


class PickInherit(models.Model):
	_inherit = 'stock.picking'

	driver_pengganti = fields.Many2one('res.users', string="Driver Pengganti")
	date_approved_by_other_driver = fields.Datetime(string="Date Approved By Other Driver")
	send_by_so = fields.Selection(
		[('grab', 'Grab'),
		 ('gojek', 'Gojek'),
		 ('lala_move', 'Lala Move'),
		 ('si_cepat', 'Sicepat'),
		 ('jnt', 'JNT'),
		 ('jne', 'JNE'),
		 ('lainnya', 'Lainnya'),
		 ],
		string='Opsi Pengiriman')

	def action_open_transfer_driver_wizard(self):
		self.ensure_one()
		return {
			'name': _('Transfer Driver'),
			'type': 'ir.actions.act_window',
			'res_model': 'transfer.driver.wizard',
			'view_mode': 'form',
			'target': 'new',
			'context': {
				'default_picking_id': self.id,
				'default_driver_pengganti_id': self.driver_pengganti.id,
			}
		}


class UrgentDelivery(models.Model):
	_name = 'urgent.delivery'
	_description = 'Urgent Delivery'
	_rec_name = 'sale_order_id'

	diajukan_oleh = fields.Many2one(
		'res.users', 
		string='Diajukan Oleh', 
		default=lambda self: self.env.user,
		required=True,
		states={'validate': [('readonly', True)], 'cancel': [('readonly', True)]}
	)
	sale_order_id = fields.Many2one(
		'sale.order', 
		string='Sales Order', 
		domain="[('send_by', '=', False)]",
		required=True,
		states={'validate': [('readonly', True)], 'cancel': [('readonly', True)]}
	)
	send_by = fields.Selection(
		[('grab', 'Grab'),
		 ('gojek', 'Gojek'),
		 ('lala_move', 'Lala Move'),
		 ('si_cepat', 'Sicepat'),
		 ('jnt', 'JNT'),
		 ('jne', 'JNE'),
		 ('lainnya', 'Lainnya'),
		 ],
		string='Opsi Pengiriman',
		required=True,
		states={'validate': [('readonly', True)], 'cancel': [('readonly', True)]}
	)
	state = fields.Selection([
		('draft', 'Draft'),
		('validate', 'Validate'),
		('cancel', 'Cancelled')
	], string='Status', default='draft', tracking=True, readonly=True)

	def action_validate(self):
		for record in self:
			if record.sale_order_id and record.send_by:
				# Update Opsi Pengiriman di Sales Order
				record.sale_order_id.write({'send_by': record.send_by})
				
				# Update Opsi Pengiriman di Stock Picking / Delivery Order yang terkait dengan SO tersebut
				pickings = self.env['stock.picking'].search([('sale_id', '=', record.sale_order_id.id)])
				for pick in pickings:
					pick.write({'send_by_so': record.send_by})
					
			record.state = 'validate'

	def action_cancel(self):
		for record in self:
			if record.sale_order_id:
				# Reset Opsi Pengiriman di Sales Order menjadi kosong (False)
				record.sale_order_id.write({'send_by': False})
				
				# Reset Opsi Pengiriman di Stock Picking / Delivery Order yang terkait
				pickings = self.env['stock.picking'].search([('sale_id', '=', record.sale_order_id.id)])
				for pick in pickings:
					pick.write({'send_by_so': False})
					
			record.state = 'cancel'

	def action_set_to_draft(self):
		for record in self:
			record.state = 'draft'


class TransferDriverWizard(models.TransientModel):
	_name = 'transfer.driver.wizard'
	_description = 'Transfer Driver Wizard'

	picking_id = fields.Many2one('stock.picking', string="Stock Picking", required=True)
	driver_pengganti_id = fields.Many2one(
		'res.users', 
		string="Driver Pengganti", 
		domain=lambda self: self._get_driver_domain(),
		required=True
	)

	@api.model
	def _get_driver_domain(self):
		group = self.env.ref('wz_report_by_coa.group_driver', raise_if_not_found=False)
		if group:
			return [('id', 'in', group.users.ids)]
		return []

	def action_confirm_transfer(self):
		self.ensure_one()
		if self.picking_id:
			self.picking_id.write({
				'driver_pengganti': self.driver_pengganti_id.id,
				'date_approved_by_other_driver': fields.Datetime.now(),
			})
		return {'type': 'ir.actions.act_window_close'}