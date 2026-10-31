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
			tag_name = tags[0] if tags else "TANPA TAG"
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
		# Akumulator total kuantitas per produk SO dari seluruh SO yang dicentang
		product_so_quantities = {} # { product_id: total_so_qty }
		for so in sales_orders:
			for line in so.order_line:
				if not line.product_id or line.product_uom_qty <= 0:
					continue
				p_id = line.product_id.id
				if p_id not in product_so_quantities:
					product_so_quantities[p_id] = 0.0
				product_so_quantities[p_id] += line.product_uom_qty

		bom_per_variant_grouped = {}
		global_bom = {}

		first_so = sales_orders[0]
		warehouse = first_so.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', first_so.company_id.id)], limit=1)

		# Ambil daftar produk unik di SO untuk dihitung BoM-nya secara akurat berdasarkan total kuantitas gabungan
		unique_so_products = self.env['product.product'].browse(list(product_so_quantities.keys()))

		for prod in unique_so_products:
			bom = self.env['mrp.bom']._bom_find(prod)[prod]
			if not bom:
				continue

			total_so_qty = product_so_quantities[prod.id]
			ctx = dict(self.env.context, warehouse_id=warehouse.id)
			
			# Ambil struktur BoM murni untuk 1 unit produk (line_qty=1.0)
			bom_data = bom_report_obj.with_context(ctx)._get_bom_data(
				bom=bom, warehouse=warehouse, product=prod, line_qty=1.0
			)

			raw_components = []
			self._collect_raw_bom_details(bom_data, raw_components)

			prod_so_name = prod.display_name
			uom_so_name = prod.uom_id.name or 'Pieces'

			if prod_so_name not in bom_per_variant_grouped:
				bom_per_variant_grouped[prod_so_name] = {
					'total_so_qty': total_so_qty,
					'uom_so': uom_so_name,
					'components_map': {}
				}

			for comp in raw_components:
				comp_prod_id = comp['product_id']
				product_obj = self.env['product.product'].browse(comp_prod_id)
				ref_code = product_obj.default_code or ''
				comp_full_name = product_obj.display_name
				bom_comp_name = product_obj.name
				uom_name = comp['uom_name']
				
				# unit_qty adalah murni per 1 unit produk dari BoM (misal: 28)
				unit_qty_per_single = comp['unit_qty']
				# total_needed adalah unit_qty dikali total kuantitas SO (misal: 28 * 8 = 224)
				total_needed = unit_qty_per_single * total_so_qty

				comp_map = bom_per_variant_grouped[prod_so_name]['components_map']
				if comp_prod_id in comp_map:
					comp_map[comp_prod_id]['qty_per_unit'] += unit_qty_per_single
					comp_map[comp_prod_id]['total_qty'] += total_needed
				else:
					comp_map[comp_prod_id] = {
						'ref_code': ref_code,
						'comp_full_name': comp_full_name,
						'bom_comp_name': bom_comp_name,
						'qty_per_unit': unit_qty_per_single,
						'uom_name': uom_name,
						'total_qty': total_needed
					}

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
		# SHEET 2: SALES ORDER DETAIL (Tag Customer Ter-merge Sesuai Kolom Partner)
		# =============================================================
		ws2 = workbook.add_worksheet('SALES ORDER DETAIL')
		ws2.set_column('A:A', 35)

		ws2.write(0, 0, "PRODUK / TAG", header_format)
		ws2.write(1, 0, "", header_format)

		p_col_map_2 = {}
		col_idx = 1
		
		tag_groups = {}
		for p_name in all_partners:
			t_name = partner_tags.get(p_name, "TANPA TAG")
			if t_name not in tag_groups:
				tag_groups[t_name] = []
			tag_groups[t_name].append(p_name)

		for tag_name, partners_in_tag in tag_groups.items():
			start_c = col_idx
			for p_name in partners_in_tag:
				ws2.write(1, col_idx, p_name, header_format)
				ws2.set_column(col_idx, col_idx, 18)
				p_col_map_2[p_name] = col_idx
				col_idx += 1
			end_c = col_idx - 1
			
			if start_c == end_c:
				ws2.write(0, start_c, tag_name, header_format)
			else:
				ws2.merge_range(0, start_c, 0, end_c, tag_name, header_format)
				for c in range(start_c + 1, end_c + 1):
					ws2.write(0, c, '', header_format)

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
		# SHEET 4: KEBUTUHAN BOM PER VARIAN (Qty per unit murni dari BoM)
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

			for comp_prod_id, comp in group_data['components_map'].items():
				ws4.write(row_idx, 0, comp['ref_code'], normal_format)
				ws4.write(row_idx, 1, comp['comp_full_name'], normal_format)
				ws4.write(row_idx, 2, comp['bom_comp_name'], normal_format)
				ws4.write(row_idx, 3, '', normal_format)
				ws4.write(row_idx, 4, comp['qty_per_unit'], num_format) # Tetap murni angka satuan per 1 unit produk dari BoM
				ws4.write(row_idx, 5, comp['uom_name'], center_format)
				ws4.write(row_idx, 6, comp['total_qty'], num_format)   # Hasil kali (qty_per_unit * total_so_qty)
				row_idx += 1
			row_idx += 1

	def _collect_raw_bom_details(self, bom_line_data, raw_components):
		components = bom_line_data.get('components', [])
		for comp in components:
			if comp.get('components'):
				self._collect_raw_bom_details(comp, raw_components)
			else:
				product_id = comp.get('product_id')
				if not product_id:
					continue
				unit_qty = comp.get('quantity', 0.0)
				uom_name = comp.get('uom_name', '')
				raw_components.append({
					'product_id': product_id,
					'unit_qty': unit_qty,
					'uom_name': uom_name
				})


	# # =========================================================================
	# # FUNCTION BARU: FAST OPTIMIZED SQL QUERY CORE BOM EXTRACTION
	# # =========================================================================
	# def generate_xlsx_report(self, workbook, data, sales_orders):
	# 	if not sales_orders:
	# 		return

	# 	# --- STYLES & FORMATS ---
	# 	header_format = workbook.add_format({
	# 		'font_name': 'Tahoma', 'font_size': 10, 'bold': True, 
	# 		'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#D3D3D3'
	# 	})
	# 	group_header_format = workbook.add_format({
	# 		'font_name': 'Tahoma', 'font_size': 10, 'bold': True, 
	# 		'align': 'left', 'valign': 'vcenter', 'border': 1, 'bg_color': '#EAEAEA'
	# 	})
	# 	normal_format = workbook.add_format({
	# 		'font_name': 'Tahoma', 'font_size': 10
	# 	})
	# 	center_format = workbook.add_format({
	# 		'font_name': 'Tahoma', 'font_size': 10, 'align': 'center'
	# 	})
	# 	num_format = workbook.add_format({
	# 		'font_name': 'Tahoma', 'font_size': 10, 'align': 'right', 'num_format': '#,##0.00'
	# 	})

	# 	# --- DATA PREPARATION ---
	# 	so_detail_data = {}
	# 	partner_tags = {}
	# 	product_totals = {}

	# 	for so in sales_orders:
	# 		partner_name = so.partner_id.name or "TANPA CUSTOMER"
	# 		tags = so.partner_id.category_id.mapped('name')
	# 		tag_name = tags[0] if tags else "TANPA TAG"
	# 		partner_tags[partner_name] = tag_name

	# 		for line in so.order_line:
	# 			if not line.product_id or line.product_uom_qty <= 0:
	# 				continue
	# 			prod_id = line.product_id.id
	# 			qty = line.product_uom_qty

	# 			if prod_id not in product_totals:
	# 				product_totals[prod_id] = 0.0
	# 			product_totals[prod_id] += qty

	# 			if prod_id not in so_detail_data:
	# 				so_detail_data[prod_id] = {}
	# 			if partner_name not in so_detail_data[prod_id]:
	# 				so_detail_data[prod_id][partner_name] = 0.0
	# 			so_detail_data[prod_id][partner_name] += qty

	# 	# Akumulasi total Qty SO per produk varian
	# 	product_so_quantities = {}
	# 	for so in sales_orders:
	# 		for line in so.order_line:
	# 			if not line.product_id or line.product_uom_qty <= 0:
	# 				continue
	# 			p_id = line.product_id.id
	# 			if p_id not in product_so_quantities:
	# 				product_so_quantities[p_id] = 0.0
	# 			product_so_quantities[p_id] += line.product_uom_qty

	# 	# --- FAST SQL BOM EXTRACTION ---
	# 	bom_per_variant_grouped = {}
	# 	global_bom = {}

	# 	unique_so_products = self.env['product.product'].browse(list(product_so_quantities.keys()))

	# 	# 1. Cari BoM ID resmi Odoo secara presisi via ORM (Sangat cepat)
	# 	product_bom_map = {} # { product_id: bom_id }
	# 	for prod in unique_so_products:
	# 		bom = self.env['mrp.bom']._bom_find(prod)[prod]
	# 		if bom:
	# 			product_bom_map[prod.id] = bom.id

	# 	# 2. Eksekusi SQL Query Rekursif berdasarkan BoM ID yang terverifikasi
	# 	if product_bom_map:
	# 		bom_ids_tuple = tuple(set(product_bom_map.values()))
			
	# 		sql_query = """
	# 			WITH RECURSIVE bom_tree AS (
	# 				-- Root Level: Ambil komponen langsung dari BoM Utama
	# 				SELECT 
	# 					bl.bom_id as root_bom_id,
	# 					bl.product_id as component_product_id,
	# 					(bl.product_qty / COALESCE(b.product_qty, 1.0)) as qty,
	# 					bl.product_uom_id as uom_id
	# 				FROM mrp_bom_line bl
	# 				JOIN mrp_bom b ON b.id = bl.bom_id
	# 				WHERE bl.bom_id IN %s
					
	# 				UNION ALL
					
	# 				-- Sub-Level: Buka sub-BoM jika komponen memiliki BoM sendiri
	# 				SELECT 
	# 					bt.root_bom_id,
	# 					sub_bl.product_id as component_product_id,
	# 					(bt.qty * sub_bl.product_qty / COALESCE(sub_b.product_qty, 1.0)) as qty,
	# 					sub_bl.product_uom_id as uom_id
	# 				FROM bom_tree bt
	# 				JOIN product_product p ON p.id = bt.component_product_id
	# 				JOIN mrp_bom sub_b ON (sub_b.product_id = p.id OR (sub_b.product_tmpl_id = p.product_tmpl_id AND sub_b.product_id IS NULL))
	# 				JOIN mrp_bom_line sub_bl ON sub_bl.bom_id = sub_b.id
	# 				WHERE sub_b.active = TRUE
	# 			)
	# 			SELECT 
	# 				bt.root_bom_id,
	# 				bt.component_product_id,
	# 				SUM(bt.qty) as unit_qty,
	# 				bt.uom_id
	# 			FROM bom_tree bt
	# 			-- Hanya ambil komponen level terbawah (daun/leaf component)
	# 			WHERE NOT EXISTS (
	# 				SELECT 1 FROM mrp_bom child_b 
	# 				JOIN product_product child_p ON child_p.id = bt.component_product_id
	# 				WHERE (child_b.product_id = child_p.id OR (child_b.product_tmpl_id = child_p.product_tmpl_id AND child_b.product_id IS NULL))
	# 				  AND child_b.active = TRUE
	# 			)
	# 			GROUP BY bt.root_bom_id, bt.component_product_id, bt.uom_id;
	# 		"""

	# 		if len(bom_ids_tuple) == 1:
	# 			self.env.cr.execute(sql_query, ( (bom_ids_tuple[0],), ))
	# 		else:
	# 			self.env.cr.execute(sql_query, (bom_ids_tuple,))

	# 		raw_sql_rows = self.env.cr.dictfetchall()

	# 		# Grouping hasil SQL berdasarkan root_bom_id
	# 		sql_bom_data = {} # { bom_id: [ {component_product_id, unit_qty, uom_id}, ... ] }
	# 		for row in raw_sql_rows:
	# 			b_id = row['root_bom_id']
	# 			if b_id not in sql_bom_data:
	# 				sql_bom_data[b_id] = []
	# 			sql_bom_data[b_id].append(row)

	# 		# Batch pre-fetch master data menggunakan ORM ringan
	# 		all_comp_ids = list(set([r['component_product_id'] for r in raw_sql_rows]))
	# 		all_uom_ids = list(set([r['uom_id'] for r in raw_sql_rows]))
			
	# 		comp_products = {p.id: p for p in self.env['product.product'].browse(all_comp_ids)}
	# 		uom_names = {u.id: u.name for u in self.env['uom.uom'].browse(all_uom_ids)}

	# 		# Olah data ke struktur Excel
	# 		for prod in unique_so_products:
	# 			bom_id = product_bom_map.get(prod.id)
	# 			if not bom_id or bom_id not in sql_bom_data:
	# 				continue

	# 			total_so_qty = product_so_quantities[prod.id]
	# 			prod_so_name = prod.display_name
	# 			uom_so_name = prod.uom_id.name or 'Pieces'

	# 			if prod_so_name not in bom_per_variant_grouped:
	# 				bom_per_variant_grouped[prod_so_name] = {
	# 					'total_so_qty': total_so_qty,
	# 					'uom_so': uom_so_name,
	# 					'components_map': {}
	# 				}

	# 			for comp_row in sql_bom_data[bom_id]:
	# 				c_prod_id = comp_row['component_product_id']
	# 				unit_qty = comp_row['unit_qty'] or 0.0
	# 				uom_name = uom_names.get(comp_row['uom_id'], 'g')

	# 				comp_obj = comp_products.get(c_prod_id)
	# 				if not comp_obj:
	# 					continue

	# 				total_needed = unit_qty * total_so_qty

	# 				comp_map = bom_per_variant_grouped[prod_so_name]['components_map']
	# 				if c_prod_id in comp_map:
	# 					comp_map[c_prod_id]['qty_per_unit'] += unit_qty
	# 					comp_map[c_prod_id]['total_qty'] += total_needed
	# 				else:
	# 					comp_map[c_prod_id] = {
	# 						'ref_code': comp_obj.default_code or '',
	# 						'comp_full_name': comp_obj.display_name,
	# 						'bom_comp_name': comp_obj.name,
	# 						'qty_per_unit': unit_qty,
	# 						'uom_name': uom_name,
	# 						'total_qty': total_needed
	# 					}

	# 				bom_comp_name = comp_obj.name
	# 				if bom_comp_name not in global_bom:
	# 					global_bom[bom_comp_name] = {'uom': uom_name, 'grand_total': 0.0}
	# 				global_bom[bom_comp_name]['grand_total'] += total_needed

	# 	so_products = sales_orders.mapped('order_line.product_id')
	# 	all_partners = sorted(list(partner_tags.keys()))

	# 	# =============================================================
	# 	# SHEET 1: RESUME SO
	# 	# =============================================================
	# 	ws1 = workbook.add_worksheet('RESUME SO')
	# 	ws1.set_column('A:A', 35)
	# 	ws1.set_column('B:B', 15)

	# 	ws1.write(0, 0, "PRODUK", header_format)
	# 	ws1.write(0, 1, "TOTAL", header_format)

	# 	row_idx = 1
	# 	for prod in so_products:
	# 		ws1.write(row_idx, 0, prod.display_name, normal_format)
	# 		tot_qty = product_totals.get(prod.id, 0.0)
	# 		ws1.write(row_idx, 1, tot_qty if tot_qty > 0 else '', num_format)
	# 		row_idx += 1

	# 	# =============================================================
	# 	# SHEET 2: SALES ORDER DETAIL
	# 	# =============================================================
	# 	ws2 = workbook.add_worksheet('SALES ORDER DETAIL')
	# 	ws2.set_column('A:A', 35)

	# 	ws2.write(0, 0, "PRODUK / TAG", header_format)
	# 	ws2.write(1, 0, "", header_format)

	# 	p_col_map_2 = {}
	# 	col_idx = 1
		
	# 	tag_groups = {}
	# 	for p_name in all_partners:
	# 		t_name = partner_tags.get(p_name, "TANPA TAG")
	# 		if t_name not in tag_groups:
	# 			tag_groups[t_name] = []
	# 		tag_groups[t_name].append(p_name)

	# 	for tag_name, partners_in_tag in tag_groups.items():
	# 		start_c = col_idx
	# 		for p_name in partners_in_tag:
	# 			ws2.write(1, col_idx, p_name, header_format)
	# 			ws2.set_column(col_idx, col_idx, 18)
	# 			p_col_map_2[p_name] = col_idx
	# 			col_idx += 1
	# 		end_c = col_idx - 1
			
	# 		if start_c == end_c:
	# 			ws2.write(0, start_c, tag_name, header_format)
	# 		else:
	# 			ws2.merge_range(0, start_c, 0, end_c, tag_name, header_format)
	# 			for c in range(start_c + 1, end_c + 1):
	# 				ws2.write(0, c, '', header_format)

	# 	ws2.merge_range(0, col_idx, 1, col_idx, "TOTAL", header_format)
	# 	ws2.set_column(col_idx, col_idx, 12)

	# 	row_idx = 2
	# 	for prod in so_products:
	# 		ws2.write(row_idx, 0, prod.display_name, normal_format)
	# 		tot_prod = 0.0
	# 		for p_name, c_idx in p_col_map_2.items():
	# 			qty = so_detail_data.get(prod.id, {}).get(p_name, 0.0)
	# 			ws2.write(row_idx, c_idx, qty if qty > 0 else '', num_format)
	# 			tot_prod += qty
	# 		ws2.write(row_idx, col_idx, tot_prod, num_format)
	# 		row_idx += 1

	# 	# =============================================================
	# 	# SHEET 3: KEBUTUHAN BOM GLOBAL
	# 	# =============================================================
	# 	ws3 = workbook.add_worksheet('KEBUTUHAN BOM GLOBAL')
	# 	ws3.set_column('A:A', 35)
	# 	ws3.set_column('B:B', 15)
	# 	ws3.set_column('C:C', 15)

	# 	ws3.write(0, 0, "BOM Component", header_format)
	# 	ws3.write(0, 1, "Unit of Measure", header_format)
	# 	ws3.write(0, 2, "Grand Total", header_format)

	# 	row_idx = 1
	# 	for comp_name, data in global_bom.items():
	# 		ws3.write(row_idx, 0, comp_name, normal_format)
	# 		ws3.write(row_idx, 1, data['uom'], normal_format)
	# 		ws3.write(row_idx, 2, data['grand_total'], num_format)
	# 		row_idx += 1

	# 	# =============================================================
	# 	# SHEET 4: KEBUTUHAN BOM PER VARIAN
	# 	# =============================================================
	# 	ws4 = workbook.add_worksheet('KEBUTUHAN BOM PER VARIAN')
	# 	ws4.set_column('A:A', 15)
	# 	ws4.set_column('B:B', 35)
	# 	ws4.set_column('C:C', 20)
	# 	ws4.set_column('D:D', 35)
	# 	ws4.set_column('E:E', 12)
	# 	ws4.set_column('F:F', 10)
	# 	ws4.set_column('G:G', 15)

	# 	row_idx = 0
	# 	for prod_so_name, group_data in bom_per_variant_grouped.items():
	# 		ws4.merge_range(row_idx, 0, row_idx, 3, prod_so_name, group_header_format)
	# 		ws4.write(row_idx, 4, group_data['total_so_qty'], header_format)
	# 		ws4.write(row_idx, 5, group_data['uom_so'], header_format)
	# 		ws4.write(row_idx, 6, "BoM", header_format)
	# 		row_idx += 1

	# 		for comp_prod_id, comp in group_data['components_map'].items():
	# 			ws4.write(row_idx, 0, comp['ref_code'], normal_format)
	# 			ws4.write(row_idx, 1, comp['comp_full_name'], normal_format)
	# 			ws4.write(row_idx, 2, comp['bom_comp_name'], normal_format)
	# 			ws4.write(row_idx, 3, '', normal_format)
	# 			ws4.write(row_idx, 4, comp['qty_per_unit'], num_format)
	# 			ws4.write(row_idx, 5, comp['uom_name'], center_format)
	# 			ws4.write(row_idx, 6, comp['total_qty'], num_format)
	# 			row_idx += 1
	# 		row_idx += 1