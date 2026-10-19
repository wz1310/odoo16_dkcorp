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
		required=True
	)
	sale_order_id = fields.Many2one(
		'sale.order', 
		string='Sales Order', 
		domain="[('send_by', '=', False)]",
		required=True
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
		required=True
	)

	@api.model
	def create(self, vals):
		res = super(UrgentDelivery, self).create(vals)
		if res.sale_order_id and res.send_by:
			res.sale_order_id.write({'send_by': res.send_by})
		return res

	def write(self, vals):
		res = super(UrgentDelivery, self).write(vals)
		for record in self:
			if record.sale_order_id and record.send_by:
				record.sale_order_id.write({'send_by': record.send_by})
		return res