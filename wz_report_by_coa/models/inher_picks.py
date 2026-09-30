# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SPicking(models.Model):
	_inherit = 'stock.picking'

	user_so = fields.Boolean(compute="_cek_user_so",default=False)
	real_driver = fields.Boolean(compute="_cek_driver",default=False)
	driver = fields.Many2one('res.users', string='Driver')
	driver_approved = fields.Char(string="Approved by Driver")
	sender_approved = fields.Char(string="Approved by Sender")
	receiver_approved = fields.Char(string="Approved by Receiver")


	def button_driver_approved(self):
		for x in self:
			x.driver_approved = x.env.user.name


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
		return res