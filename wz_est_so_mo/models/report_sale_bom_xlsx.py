# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class ReportSaleBomResumeXlsx(models.AbstractModel):
	_name = 'report.wz_int_tf_report.report_sale_bom_resume_xlsx'
	_inherit = 'report.report_xlsx.abstract'
	_description = 'Resume Sales Order & Kebutuhan BoM XLSX'

	def generate_xlsx_report(self, workbook, data, sales_orders):
		if not sales_orders:
			return

		bom_report_obj = self.env['report.mrp.report_bom_structure']

		# --- STYLES & FORMATS ---
		header_format = workbook.add_format({
			'font_name': 'Tahoma', 'font_size': 10, 'bold': True, 
			'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#D3D3D3'
		})
		group_header_format = workbook.add_format({
			'font_name': 'Tahoma', 'font_size': 10, 'bold': True, 
			'align': 'left', 'valign': 'vcenter', 'border': 1, 'bg_color': '#EAEAEA'
		})
		normal_format = workbook.add_format({
			'font_name': 'Tahoma', 'font_size': 10
		})
		center_format = workbook.add_format({
			'font_name': 'Tahoma', 'font_size': 10, 'align': 'center'
		})
		num_format = workbook.add_format({
			'font_name': 'Tahoma', 'font_size': 10, 'align': 'right', 'num_format': '#,##0.00'
		})

		# --- DATA PREPARATION ---
		so_detail_data = {} # { prod_id: { partner_full_name: qty } }
		partner_tags = {}   # { partner_full_name: tag_name }
		product_totals = {} # { prod_id: total_qty }

		for so in sales_orders:
			partner_name = so.partner_id.name or "TANPA CUSTOMER"
			tags = so.partner_id.category_id.mapped('name')
			tag_name = tags[0] if tags else ""
			partner_tags[partner_name] = tag_name

			for line in so.order_line:
				if not line.product_id or line.product_uom_qty <= 0:
					continue
				prod_id = line.product_id.id
				qty = line.product_uom_qty

				# Resume Total Data (Sheet 1)
				if prod_id not in product_totals:
					product_totals[prod_id] = 0.0
				product_totals[prod_id] += qty

				# Detail Data (Sheet 2)
				if prod_id not in so_detail_data:
					so_detail_data[prod_id] = {}
				if partner_name not in so_detail_data[prod_id]:
					so_detail_data[prod_id][partner_name] = 0.0
				so_detail_data[prod_id][partner_name] += qty

		# --- BOM CALCULATIONS ---
		bom_per_variant_grouped = {}
		global_bom = {}

		first_so = sales_orders[0]
		warehouse = first_so.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', first_so.company_id.id)], limit=1)

		for so in sales_orders:
			for line in so.order_line:
				if not line.product_id or line.product_uom_qty <= 0:
					continue
				bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]
				if not bom:
					continue

				ctx = dict(self.env.context, warehouse_id=warehouse.id)
				bom_data = bom_report_obj.with_context(ctx)._get_bom_data(
					bom=bom, warehouse=warehouse, product=line.product_id, line_qty=1.0
				)

				raw_components = []
				self._collect_raw_bom_details(bom_data, raw_components, line.product_uom_qty)

				prod_so_name = line.product_id.display_name
				if prod_so_name not in bom_per_variant_grouped:
					bom_per_variant_grouped[prod_so_name] = {
						'total_so_qty': line.product_uom_qty,
						'uom_so': line.product_uom.name or 'Pieces',
						'components': []
					}
				else:
					bom_per_variant_grouped[prod_so_name]['total_so_qty'] += line.product_uom_qty

				for comp in raw_components:
					product_obj = self.env['product.product'].browse(comp['product_id'])
					ref_code = product_obj.default_code or ''
					comp_full_name = product_obj.display_name
					bom_comp_name = product_obj.name
					uom_name = comp['uom_name']
					qty_per_unit = comp['unit_qty']
					total_needed = comp['qty']

					bom_per_variant_grouped[prod_so_name]['components'].append({
						'ref_code': ref_code,
						'comp_full_name': comp_full_name,
						'bom_comp_name': bom_comp_name,
						'qty_per_unit': qty_per_unit,
						'uom_name': uom_name,
						'total_qty': total_needed
					})

					if bom_comp_name not in global_bom:
						global_bom[bom_comp_name] = {'uom': uom_name, 'grand_total': 0.0}
					global_bom[bom_comp_name]['grand_total'] += total_needed

		so_products = sales_orders.mapped('order_line.product_id')
		all_partners = sorted(list(partner_tags.keys()))

		# =============================================================
		# SHEET 1: RESUME SO (Hanya 2 Kolom: Produk & Total)
		# =============================================================
		ws1 = workbook.add_worksheet('RESUME SO')
		ws1.set_column('A:A', 35)
		ws1.set_column('B:B', 15)

		ws1.write(0, 0, "PRODUK", header_format)
		ws1.write(0, 1, "TOTAL", header_format)

		row_idx = 1
		for prod in so_products:
			ws1.write(row_idx, 0, prod.display_name, normal_format)
			tot_qty = product_totals.get(prod.id, 0.0)
			ws1.write(row_idx, 1, tot_qty if tot_qty > 0 else '', num_format)
			row_idx += 1

		# =============================================================
		# SHEET 2: SALES ORDER DETAIL (Dengan Baris Tag Customer di Atas Nama Customer)
		# =============================================================
		ws2 = workbook.add_worksheet('SALES ORDER DETAIL')
		ws2.set_column('A:A', 35)

		# Row 0: Tag Customer Header
		ws2.write(0, 0, "PRODUK / TAG", header_format)
		
		# Row 1: Nama Customer Full Header
		ws2.write(1, 0, "", header_format)

		p_col_map_2 = {}
		col_idx = 1
		for p_name in all_partners:
			tag_val = partner_tags.get(p_name, "")
			ws2.write(0, col_idx, tag_val, header_format) # Tag Customer di atas
			ws2.write(1, col_idx, p_name, header_format) # Nama Customer Full di bawahnya
			ws2.set_column(col_idx, col_idx, 18)
			p_col_map_2[p_name] = col_idx
			col_idx += 1

		ws2.merge_range(0, col_idx, 1, col_idx, "TOTAL", header_format)
		ws2.set_column(col_idx, col_idx, 12)

		row_idx = 2
		for prod in so_products:
			ws2.write(row_idx, 0, prod.display_name, normal_format)
			tot_prod = 0.0
			for p_name, c_idx in p_col_map_2.items():
				qty = so_detail_data.get(prod.id, {}).get(p_name, 0.0)
				ws2.write(row_idx, c_idx, qty if qty > 0 else '', num_format)
				tot_prod += qty
			ws2.write(row_idx, col_idx, tot_prod, num_format)
			row_idx += 1

		# =============================================================
		# SHEET 3: KEBUTUHAN BOM GLOBAL
		# =============================================================
		ws3 = workbook.add_worksheet('KEBUTUHAN BOM GLOBAL')
		ws3.set_column('A:A', 35)
		ws3.set_column('B:B', 15)
		ws3.set_column('C:C', 15)

		ws3.write(0, 0, "BOM Component", header_format)
		ws3.write(0, 1, "Unit of Measure", header_format)
		ws3.write(0, 2, "Grand Total", header_format)

		row_idx = 1
		for comp_name, data in global_bom.items():
			ws3.write(row_idx, 0, comp_name, normal_format)
			ws3.write(row_idx, 1, data['uom'], normal_format)
			ws3.write(row_idx, 2, data['grand_total'], num_format)
			row_idx += 1

		# =============================================================
		# SHEET 4: KEBUTUHAN BOM PER VARIAN (Dengan Grouping per Varian SO)
		# =============================================================
		ws4 = workbook.add_worksheet('KEBUTUHAN BOM PER VARIAN')
		ws4.set_column('A:A', 15)
		ws4.set_column('B:B', 35)
		ws4.set_column('C:C', 20)
		ws4.set_column('D:D', 35)
		ws4.set_column('E:E', 12)
		ws4.set_column('F:F', 10)
		ws4.set_column('G:G', 15)

		row_idx = 0
		for prod_so_name, group_data in bom_per_variant_grouped.items():
			ws4.merge_range(row_idx, 0, row_idx, 3, prod_so_name, group_header_format)
			ws4.write(row_idx, 4, group_data['total_so_qty'], header_format)
			ws4.write(row_idx, 5, group_data['uom_so'], header_format)
			ws4.write(row_idx, 6, "BoM", header_format)
			row_idx += 1

			for comp in group_data['components']:
				ws4.write(row_idx, 0, comp['ref_code'], normal_format)
				ws4.write(row_idx, 1, comp['comp_full_name'], normal_format)
				ws4.write(row_idx, 2, comp['bom_comp_name'], normal_format)
				ws4.write(row_idx, 3, '', normal_format)
				ws4.write(row_idx, 4, comp['qty_per_unit'], num_format)
				ws4.write(row_idx, 5, comp['uom_name'], center_format)
				ws4.write(row_idx, 6, comp['total_qty'], num_format)
				row_idx += 1
			row_idx += 1

	def _collect_raw_bom_details(self, bom_line_data, raw_components, so_qty=1.0):
		components = bom_line_data.get('components', [])
		for comp in components:
			if comp.get('components'):
				self._collect_raw_bom_details(comp, raw_components, so_qty)
			else:
				product_id = comp.get('product_id')
				if not product_id:
					continue
				unit_qty = comp.get('quantity', 0.0)
				uom_name = comp.get('uom_name', '')
				raw_components.append({
					'product_id': product_id,
					'unit_qty': unit_qty,
					'qty': unit_qty * so_qty,
					'uom_name': uom_name
				})