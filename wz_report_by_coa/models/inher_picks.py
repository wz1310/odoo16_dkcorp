# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError,UserError


class SPicking(models.Model):
	_inherit = 'stock.picking'

	user_so = fields.Boolean(compute="_cek_user_so",default=False)
	real_driver = fields.Boolean(compute="_cek_driver",default=False)
	driver = fields.Many2one('res.users', string='Driver',domain=lambda self: [('groups_id', 'in', [self.env.ref('wz_report_by_coa.group_driver').id])])
	driver_approved = fields.Char(string="Approved by Driver")
	cek_driver_approved = fields.Boolean()
	sender_approved = fields.Char(string="Approved by Sender")
	receiver_approved = fields.Char(string="Approved by Receiver")
	date_driver_approved = fields.Datetime(string="Date Approved by Driver")
	date_sender_approved = fields.Datetime(string="Date Approved by Sender")
	date_receiver_approved = fields.Datetime(string="Date Approved by Receiver")


	def button_driver_approved(self):
		for x in self:
			x.cek_driver_approved = False
			if x.driver:
				x.driver_approved = x.driver.name
				x.date_driver_approved = fields.Datetime.now()
				x.cek_driver_approved = True
			else:
				raise UserError(_("Please fill the driver first."))


	def _cek_user_so(self):
		for x in self:
			x.user_so = False
			if x.env.user.id == x.sale_id.create_uid.id:
				x.user_so = True


	def _cek_driver(self):
		for x in self:
			x.real_driver = False
			if x.env.user.id == x.driver.id or x.env.user.id == x.sale_id.create_uid.id:
				x.real_driver = True

	def button_validate_custom(self):
		res = super(SPicking, self).button_validate_custom()
		for x in self:
			x.sender_approved = x.env.user.name
			x.date_sender_approved = fields.Datetime.now()
		return res

	def receive_do(self):
		res = super(SPicking, self).receive_do()
		for x in self:
			x.date_receiver_approved = fields.Datetime.now()
		return res