import datetime
import json
import math
import requests
import pytz  # <-- Tambahkan import pytz untuk konversi zona waktu
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
		
		# Mengatur zona waktu ke WIB (Asia/Jakarta)
		# Jika ingin otomatis mengikuti zona waktu user yang sedang login, bisa pakai: self.env.user.tz or 'Asia/Jakarta'
		user_tz = pytz.timezone('Asia/Jakarta')
		
		if self.date_order:
			# Odoo menyimpan date_order dalam bentuk UTC (naive datetime)
			utc_dt = pytz.utc.localize(self.date_order)
			# Konversi ke waktu lokal Indonesia (WIB)
			local_dt = utc_dt.astimezone(user_tz)
			
			order_date = local_dt.strftime('%d-%m-%Y')
			order_time = local_dt.strftime('%H:%M:%S')
		else:
			order_date = '-'
			order_time = '-'
		
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
			f"Tanggal {order_date} jam {order_time} WIB\n"  # Ditambahkan keterangan WIB
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
			print("response", response)
			response.raise_for_status()
		except Exception as e:
			pass

	def send_schedule_resume_tele(self):
		"""
		Fungsi untuk mengirimkan resume Sales Order harian secara penuh (per hari ini)
		dijalankan melalui schedule manual, lengkap dengan tombol inline URL ke Odoo
		menggunakan dynamic action untuk memastikan filter domain dan grouping berjalan.
		"""
		# 1. Ambil konfigurasi URL dan Chat ID dari System Parameters
		url_tele = self.env['ir.config_parameter'].sudo().search([('key', '=', 'url_tele_notif_sales')]).value
		chatid_number = self.env['ir.config_parameter'].sudo().search([('key', '=', 'chatid_sales')]).value
		
		if not url_tele or not chatid_number:
			return # Keluar jika konfigurasi belum diset

		# 2. Tentukan rentang waktu penuh hari ini (00:00:00 s.d 23:59:59 WIB) dikonversi ke UTC
		user_tz = pytz.timezone('Asia/Jakarta')
		now_local = datetime.datetime.now(user_tz)
		
		start_local_dt = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
		end_local_dt = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
		
		start_utc_dt = start_local_dt.astimezone(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
		end_utc_dt = end_local_dt.astimezone(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

		# 3. Eksekusi Query SQL untuk performa yang lebih ringan dan optimal (Filter penuh hari ini)
		query = """
			SELECT 
				rp.name AS customer_name,
				COALESCE(SUM(sol.product_uom_qty), 0.0) AS total_qty
			FROM sale_order so
			JOIN res_partner rp ON so.partner_id = rp.id
			JOIN sale_order_line sol ON sol.order_id = so.id
			WHERE so.state = 'sale'
			  AND so.date_order >= %s
			  AND so.date_order <= %s
			GROUP BY rp.name
			ORDER BY rp.name;
		"""
		self.env.cr.execute(query, (start_utc_dt, end_utc_dt))
		results = self.env.cr.fetchall()

		if not results:
			# Jika tidak ada data SO pada hari ini
			return

		# 4. Susun bagian teks untuk masing-masing customer dan hitung total akumulasi SO
		customer_lines = ""
		total_akumulasi_so = 0.0

		for row in results:
			customer_name = row[0]
			total_qty = row[1]
			total_akumulasi_so += total_qty
			customer_lines += f"Total SO {customer_name} {total_qty}\n"

		# 5. Hitung Jumlah Kebutuhan Tenaga Kerja berdasarkan formula SO (mrp.worker.formula)
		formula = self.env['mrp.worker.formula'].search([], limit=1)
		jumlah_tenaga_kerja = 0
		if formula and formula.qty_base > 0:
			multiplier = math.ceil(total_akumulasi_so / formula.qty_base)
			jumlah_tenaga_kerja = multiplier * formula.worker_count

		# Format tanggal untuk header pesan (misal: 15-10-2026)
		date_str = now_local.strftime('%d-%m-%Y')

		# 6. Menyusun template pesan Telegram sesuai permintaan
		message_text = (
			f"Resume SO {date_str}\n\n"
			f"{customer_lines}\n"
			f"Sehingga Total Akumulasi SO adalah {total_akumulasi_so}\n"
			f"Jumlah Kebutuhan Tenaga Kerja {jumlah_tenaga_kerja}\n\n"
			f"Silahkan ditindak lanjuti!"
		)

		# 7. Ambil Base URL Odoo & Buat Action Window Dinamis agar Domain & Grouping Terbawa
		base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
		base_url = base_url.replace('http://', 'https://')
		
		payload = {
			"chat_id": chatid_number,
			"text": message_text,
			"parse_mode": "HTML"
		}

		if base_url and 'localhost' not in base_url and '127.0.0.1' not in base_url:
			# Definisikan domain filter tanggal hari ini dan context group_by partner
			domain_list = [('state', '=', 'sale'), ('date_order', '>=', start_utc_dt), ('date_order', '<=', end_utc_dt)]
			context_dict = {'group_by': 'partner_id'}
			
			action_vals = {
				'name': f'Resume SO {date_str}',
				'res_model': 'sale.order',
				'view_mode': 'tree,kanban,form',
				'domain': str(domain_list),
				'context': str(context_dict),
				'target': 'current',
			}
			# Membuat record action window baru di database secara dinamis
			action = self.env['ir.actions.act_window'].sudo().create(action_vals)
			action_id = action.id
			
			odoo_so_url = f"{base_url.rstrip('/')}/web#action={action_id}&model=sale.order&view_type=list"
			
			payload["reply_markup"] = {
				"inline_keyboard": [
					[
						{
							"text": "Lihat List SO di Odoo",
							"url": odoo_so_url
						}
					]
				]
			}
		
		headers = {'Content-Type': 'application/json'}
		
		try:
			response = requests.post(url_tele, headers=headers, data=json.dumps(payload), timeout=10)
			print("response schedule resume", response.text)
			response.raise_for_status()
		except Exception as e:
			print("Error Telegram Schedule:", str(e))
			pass