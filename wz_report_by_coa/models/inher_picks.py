# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SPicking(models.Model):
	_inherit = 'stock.picking'

	user_so = fields.Boolean(compute="_cek_user_so",default=False)
	real_driver = fields.Boolean(compute="_cek_driver",default=False)
	driver = fields.Many2one('res.users', string='Driver')


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