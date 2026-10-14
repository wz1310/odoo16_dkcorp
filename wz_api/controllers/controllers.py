import datetime
import json
import requests
from odoo import models, fields, api, _

class ScheduleTele(models.Model):
	_inherit = 'sale.order'

	# Override method write untuk mendeteksi perubahan status menjadi 'sale'
	def write(self, vals):
		res = super(ScheduleTele, self).write(vals)
		# Cek apakah state berubah menjadi 'sale'
		if vals.get('state') == 'sale':
			for order in self:
				order.send_tele()
		return res

	def send_tele(self):
		print("JALAN APIIIII")
		self.ensure_one()
		
		# Ambil konfigurasi URL dan Chat ID dari System Parameters
		url_tele = self.env['ir.config_parameter'].sudo().search([('key', '=', 'url_tele_notif_sales')]).value
		chatid_number = self.env['ir.config_parameter'].sudo().search([('key', '=', 'chatid_sales')]).value
		
		if not url_tele or not chatid_number:
			return # Keluar jika konfigurasi belum diset
		
		# Format Tanggal & Waktu pemesanan (menggunakan waktu lokal / create_date atau date_order)
		order_date = self.date_order.strftime('%d-%m-%Y') if self.date_order else '-'
		order_time = self.date_order.strftime('%H:%M:%S') if self.date_order else '-'
		
		# Mengambil nama user yang melakukan konfirmasi / user yang sedang login saat ini
		user_name = self.env.user.name or '-'

		# Mengambil nama-nama tag/kategori dari partner (category_id adalah field many2many)
		partner_tags = ", ".join(self.partner_id.category_id.mapped('name')) if self.partner_id.category_id else '-'

		# Menyusun baris detail produk
		product_lines = ""
		for line in self.order_line:
			name = line.product_id.name or '-'
			qty = line.product_uom_qty or 0.0
			uom = line.product_uom.name or '-'
			# Format rapi per baris produk
			product_lines += f"- {name} | Qty: {qty} {uom}\n"

		# Menyusun teks pesan (menggunakan format teks Telegram / Markdown)
		message_text = (
			f"<b>Sale Order: {partner_tags}</b>\n"
			f"Tanggal {order_date} jam {order_time}\n"
			f"Dibuat Oleh: {user_name}\n\n"
			f"{self.name} | {self.partner_id.name}\n"
			f"<b>Detail Order</b>\n"
			f"================\n"
			f"{product_lines}"
		)

		# Payload JSON untuk Telegram (menggunakan parse_mode HTML agar format bold/code rapi)
		payload = json.dumps({
			"chat_id": chatid_number,
			"text": message_text,
			"parse_mode": "HTML"
		})
		
		headers = {'Content-Type': 'application/json'}
		
		try:
			response = requests.post(url_tele, headers=headers, data=payload, timeout=10)
			print("response",response)
			response.raise_for_status()
		except Exception as e:
			# Anda bisa menambahkan logging error jika diperlukan
			pass