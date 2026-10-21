# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class NotifSales(models.Model):
	_inherit = 'sale.order'

	manager_approved = fields.Boolean(string='Manager Approved', default=False)

	def action_manager_approve(self):
		for order in self:
			order.manager_approved = True
			user_name = self.env.user.name
			order.message_post(body=_(f"Sale Order ini disetujui oleh {user_name}"))
		return True

	@api.model
	def get_pending_manager_approval_count(self):
		"""Query ringan untuk menghitung SO hari ini dan mengambil setting interval dari ir.config_parameter"""
		if not self.env.user.has_group('wz_notif_so.group_sale_manager_notif'):
			return {'count': 0, 'interval': 0}

		# Mengambil nilai interval dari ir.config_parameter
		param_interval = self.env['ir.config_parameter'].sudo().get_param('interval_notif_so')
		
		# Jika parameter belum diset atau kosong, kembalikan interval 0 agar tidak tampil
		if not param_interval or not param_interval.isdigit():
			return {'count': 0, 'interval': 0}

		interval_ms = int(param_interval) * 1000  # Konversi detik ke milidetik untuk JS

		current_date = fields.Date.context_today(self)
		
		query = """
			SELECT count(id) 
			FROM sale_order 
			WHERE state = 'sale' 
			  AND (manager_approved = FALSE OR manager_approved IS NULL)
			  AND date_order::date = %s
		"""
		self.env.cr.execute(query, (current_date,))
		res = self.env.cr.fetchone()
		count = res[0] if res else 0

		return {'count': count, 'interval': interval_ms}

	@api.model
	def get_pending_manager_approval_action_id(self):
		"""Membuat ir.actions.act_window secara dinamis agar domain filter hari ini & approval terbawa sempurna"""
		current_date = fields.Date.context_today(self)
		
		start_datetime = f"{current_date} 00:00:00"
		end_datetime = f"{current_date} 23:59:59"

		domain_list = [
			('state', '=', 'sale'),
			('manager_approved', '=', False),
			('date_order', '>=', start_datetime),
			('date_order', '<=', end_datetime)
		]

		action_vals = {
			'name': f'Pending Manager Approval SO ({current_date})',
			'res_model': 'sale.order',
			'view_mode': 'tree,form',
			'views': [(False, 'list'), (False, 'form')],
			'domain': str(domain_list),
			'target': 'current',
		}
		
		# Membuat record action window baru di database secara dinamis
		action = self.env['ir.actions.act_window'].sudo().create(action_vals)
		return action.id