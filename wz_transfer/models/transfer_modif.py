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

	driver_pengganti = fields.Many2one('res.users',string="Driver Pengganti")
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