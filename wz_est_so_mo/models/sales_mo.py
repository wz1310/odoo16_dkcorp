# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_round

import logging
_logger = logging.getLogger(__name__)

class EstSalesMo(models.Model):
    _inherit = 'sale.order'


    def create_int_bom(self):
        self.ensure_one()
        bom_report_obj = self.env['report.mrp.report_bom_structure']
        warehouse = self.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_("Gudang (Warehouse) tidak ditemukan untuk dokumen ini."))
        source_location = warehouse.int_type_id.default_location_src_id or warehouse.lot_stock_id
        final_components = []
        location_tf = self.env['ir.config_parameter'].sudo().search([('key','=','internal_bom')]).value
        for line in self.order_line:
            if not line.product_id:
                continue
            bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]
            if not bom:
                continue
            bom_data = bom_report_obj._get_bom_data(
                bom=bom,
                warehouse=warehouse,
                product=line.product_id,
                # line_qty=line.product_uom_qty
                line_qty=1.0 # Set ke 1.0 agar kita mendapatkan unit murni per 1 unit produk jadi
                )
            self._collect_final_bom_components(bom_data, final_components,line.product_uom_qty)
        if not final_components:
            raise UserError(_("Tidak ada komponen BoM layer terakhir yang ditemukan untuk dibuatkan transfer."))

        grouped_lines = {}
        for comp in final_components:
            product_id = comp['product_id']
            qty = comp['qty']
            uom_id = comp['uom_id']
            if product_id in grouped_lines:
                grouped_lines[product_id]['qty'] += qty
            else:
                grouped_lines[product_id] = {'qty': qty, 'uom_id': uom_id}
        picking_vals = {
            'picking_type_id': warehouse.int_type_id.id,
            'location_id': source_location.id,
            'location_dest_id': int(location_tf) if location_tf else source_location.id,
            'origin': self.name,
            'sale_id': self.id,
            }
        new_picking = self.env['stock.picking'].create(picking_vals)
        move_lines = []
        for prod_id, data in grouped_lines.items():
            # print("UOMMM",data['uom_id'])
            # print("QTY",data['qty'])
            move_lines.append((0, 0, {
                'name': self.name,
                'product_id': prod_id,
                'product_uom_qty': data['qty'],
                'product_uom': data['uom_id'],
                'location_id': source_location.id,
                'location_dest_id': int(location_tf) if location_tf else source_location.id,
                }))
        new_picking.write({'move_ids_without_package': move_lines})
        return {
            'name': _('Internal Transfer Generated'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': new_picking.id,
            'target': 'current',
            }

    def _collect_final_bom_components(self, bom_line_data, final_components,so_qty=1.0):
        components = bom_line_data.get('components', [])
        for comp in components:
            if comp.get('components'):
                self._collect_final_bom_components(comp, final_components,so_qty)
            else:
                product_id = comp.get('product_id')
                if not product_id:
                    continue
                uom_id = comp.get('uom_id') or comp.get('product_uom_id')
                if not uom_id:
                    product = self.env['product.product'].browse(product_id)
                    uom_id = product.uom_id.id
                
                # base_qty = comp.get('base_bom_line_qty', 0.0)
                # total_needed_qty = base_qty * so_qty
                # --- PERBAIKAN: MENGAMBIL KEY QUANTITY MURNI OVERVIEW ---
                # Key 'quantity' di level komponen mencerminkan angka yang tampil di layar BoM Overview
                bom_qty = comp.get('quantity', 0.0)
                total_needed_qty = bom_qty * so_qty
                
                final_components.append({
                    'product_id': product_id,
                    'qty': total_needed_qty,
                    'uom_id': uom_id,
                    })


    def _print_bom_components_recursive(self, bom_line_data, level=1):
        components = bom_line_data.get('components', [])

        for comp in components:
            indentation = "    " * level
            comp_name = comp.get('name', 'Unknown Product')
            comp_type = comp.get('type', 'component')
            bom_qty = comp.get('base_bom_line_qty', 0.0)
            uom_name = comp.get('uom_name', '')

            if comp.get('components'):
                self._print_bom_components_recursive(comp, level + 1)
            else:
                indentation = "    " * level
                print(f"{indentation}- [{comp_type.upper()}] {comp_name} (Butuh: {bom_qty} {uom_name})")
                # _logger.info(f"{indentation}- [{comp_type.upper()}] {comp_name} (Butuh: {bom_qty} {uom_name})")

            # if comp.get('components'):
            #     self._print_bom_components_recursive(comp, level + 1)

    def cek_last_bom(self):
        bom_report_obj = self.env['report.mrp.report_bom_structure']
        print("\n=== START CEK LIST BOM YANG DIBUTUHKAN ===")
        for line in self.order_line:
            if not line.product_id:
                continue

            bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]

            print(f"\nProduk Utama Order Line: {line.product_id.name}")
            # _logger.info(f"Produk Utama Order Line: {line.product_id.name}")
            if not bom:
                print("    -> Produk ini tidak memiliki Bill of Materials (BOM).")
                continue
            warehouse = self.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
            bom_data = bom_report_obj._get_bom_data(
                bom=bom,
                warehouse=warehouse,
                product=line.product_id,
                line_qty=1.0)
            self._print_bom_components_recursive(bom_data, level=1)
        print("=== END CEK LIST BOM YANG DIBUTUHKAN ===\n")


    # def _get_component_producible_qty(self, bom_line_data):
    #     """
    #     Fungsi rekursif murni untuk mencari kapasitas produksi maksimum komponen.
    #     Menghitung kapasitas riil dari tingkat terbawah tanpa double-counting.
    #     """
    #     # Jika komponen tidak memiliki sub-BOM lagi (daun terbawah dari pohon BoM)
    #     if not bom_line_data.get('components'):
    #         # Langsung ambil kapasitas yang disediakan Odoo (producible_qty) atau stok on hand-nya
    #         # Di level daun, producible_qty mencerminkan ketersediaan material dasar tersebut
    #         return bom_line_data.get('producible_qty', 0.0) or bom_line_data.get('quantity_available', 0.0)

    #     # Jika komponen merupakan Sub-BOM (seperti Wood Panel atau Storage Box)
    #     sub_capacities = []
    #     for comp in bom_line_data.get('components', []):
    #         # Hitung kapasitas pasokan dari anak-anak komponen di bawahnya
    #         child_producible = self._get_component_producible_qty(comp)
            
    #         # Berapa unit 'Sub-BOM' ini yang bisa dibuat oleh anak tersebut?
    #         base_bom_qty = comp.get('base_bom_line_qty', 0.0)
    #         if base_bom_qty > 0:
    #             # Contoh: 6 Plastic Laminate / 3 kebutuhan = 2 Storage Box
    #             capacity_for_parent = float_round(child_producible / base_bom_qty, precision_digits=0, rounding_method='DOWN')
    #             sub_capacities.append(capacity_for_parent)
    #         else:
    #             sub_capacities.append(0.0)

    #     # Cari batasan terkecil (bottleneck) dari seluruh anak komponennya
    #     min_from_children = min(sub_capacities) if sub_capacities else 0.0
        
    #     # Kapasitas total Sub-BOM ini = Stok fisik Sub-BOM yang sudah jadi + hasil rakitan dari bawahnya
    #     current_available = bom_line_data.get('quantity_available', 0.0)
    #     return current_available + min_from_children

    # def action_cek_est(self):
    #     bom_report_obj = self.env['report.mrp.report_bom_structure']
        
    #     for line in self.order_line:
    #         if not line.product_id:
    #             continue
                
    #         bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]
            
    #         if not bom:
    #             line.est = line.product_id.free_qty if hasattr(line.product_id, 'free_qty') else line.product_id.qty_available
    #             continue
            
    #         warehouse = self.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
            
    #         # Panggil struktur data BoM Overview resmi Odoo
    #         bom_data = bom_report_obj._get_bom_data(
    #             bom=bom, 
    #             warehouse=warehouse, 
    #             product=line.product_id, 
    #             line_qty=1.0
    #         )
            
    #         # 1. Stok produk utama yang langsung siap pakai di gudang (Acoustic Bloc Screens = 16)
    #         qty_on_hand_jadi = bom_data.get('quantity_available', 0.0)
            
    #         # 2. Hitung berapa unit baru produk utama yang bisa dirakit dari komponen tingkat pertama (Level 1)
    #         producible_list = []
    #         for comp in bom_data.get('components', []):
    #             # Hitung pasokan total yang bisa diberikan oleh komponen/sub-bom ini ke atas
    #             total_component_supply = self._get_component_producible_qty(comp)
                
    #             # Berapa banyak Produk Utama yang bisa disuplai oleh total komponen ini?
    #             base_bom_qty = comp.get('base_bom_line_qty', 0.0)
    #             if base_bom_qty > 0:
    #                 producible_list.append(float_round(total_component_supply / base_bom_qty, precision_digits=0, rounding_method='DOWN'))

    #         # Ambil nilai komponen yang paling membatasi produksi
    #         qty_ready_to_produce = min(producible_list) if producible_list else 0.0
            
    #         # 3. Total Estimasi Akhir = Sisa Stok Jadi + Potensi Produksi Baru
    #         line.est = qty_on_hand_jadi + qty_ready_to_produce

    #         if (qty_on_hand_jadi + qty_ready_to_produce) > line.product_uom_qty:
    #             line.est = line.product_uom_qty
    #         if (qty_on_hand_jadi + qty_ready_to_produce) <= 0:
    #             line.est = 0
            
    #         _logger.info(f"Product: {line.product_id.name} | On Hand: {qty_on_hand_jadi} | Deep Ready: {qty_ready_to_produce} | Total Est: {line.est}")

    def _get_component_producible_qty(self, bom_line_data, context_lokasi):
        """
        Fungsi rekursif murni untuk mencari kapasitas produksi maksimum komponen.
        Ditambahkan parameter context_lokasi agar ORM Odoo membaca lokasi yang tepat.
        """
        product_id = bom_line_data.get('product_id')
        if not product_id:
            return 0.0

        # Jika komponen tidak memiliki sub-BOM lagi (daun terbawah)
        if not bom_line_data.get('components'):
            # --- FORCE RE-READ DENGAN CONTEXT LOKASI YANG BENAR ---
            # Jangan percaya 100% pada data dictionary bawaan Odoo jika sering bocor antar warehouse.
            # Kita paksa ambil quantity_available dari database berdasarkan context warehouse/location SO.
            product = self.env['product.product'].browse(product_id).with_context(context_lokasi)
            
            # Gunakan free_qty (Available) atau qty_available (On Hand) sesuai kebutuhan bisnis Anda
            return product.free_qty if hasattr(product, 'free_qty') else product.qty_available

        # Jika komponen merupakan Sub-BOM
        sub_capacities = []
        for comp in bom_line_data.get('components', []):
            # Teruskan context_lokasi ke anak komponen di bawahnya
            child_producible = self._get_component_producible_qty(comp, context_lokasi)
            
            base_bom_qty = comp.get('base_bom_line_qty', 0.0)
            if base_bom_qty > 0:
                capacity_for_parent = float_round(child_producible / base_bom_qty, precision_digits=0, rounding_method='DOWN')
                sub_capacities.append(capacity_for_parent)
            else:
                sub_capacities.append(0.0)

        min_from_children = min(sub_capacities) if sub_capacities else 0.0
        
        # Ambil stok fisik Sub-BOM ini dari database dengan context lokasi yang benar
        parent_product = self.env['product.product'].browse(product_id).with_context(context_lokasi)
        current_available = parent_product.free_qty if hasattr(parent_product, 'free_qty') else parent_product.qty_available
        
        return current_available + min_from_children


    def action_cek_est(self):
        bom_report_obj = self.env['report.mrp.report_bom_structure']
        
        for line in self.order_line:
            if not line.product_id:
                continue
                
            bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]
            warehouse = self.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
            
            # Buat context super ketat mengunci lokasi internal stock warehouse SO (e.g., WH/Stock)
            ctx = dict(
                self.env.context, 
                warehouse_id=warehouse.id, 
                warehouse=warehouse.id,
                location=warehouse.lot_stock_id.id,
                location_id=warehouse.lot_stock_id.id
            )

            if not bom:
                product_ctx = line.product_id.with_context(ctx)
                line.est = product_ctx.free_qty if hasattr(product_ctx, 'free_qty') else product_ctx.qty_available
                continue

            # Panggil struktur data BoM Overview resmi Odoo dengan context ketat
            bom_data = bom_report_obj.with_context(ctx)._get_bom_data(
                bom=bom, 
                warehouse=warehouse, 
                product=line.product_id, 
                line_qty=1.0
            )
            
            # Paksa baca ulang stok produk utama jadi langsung dari database via context (agar sinkron dengan layar)
            main_product_ctx = line.product_id.with_context(ctx)
            qty_on_hand_jadi = main_product_ctx.free_qty if hasattr(main_product_ctx, 'free_qty') else main_product_ctx.qty_available
            
            # Hitung kapasitas komponen (Level 1 dst)
            producible_list = []
            for comp in bom_data.get('components', []):
                # Kirim ctx ke fungsi rekursif
                total_component_supply = self._get_component_producible_qty(comp, ctx)
                
                base_bom_qty = comp.get('base_bom_line_qty', 0.0)
                if base_bom_qty > 0:
                    producible_list.append(float_round(total_component_supply / base_bom_qty, precision_digits=0, rounding_method='DOWN'))

            qty_ready_to_produce = min(producible_list) if producible_list else 0.0
            
            # Total Estimasi Akhir = Sisa Stok Jadi + Potensi Produksi Baru
            total_est = qty_on_hand_jadi + qty_ready_to_produce

            # Batasi sesuai quantity order line jika melebihi
            if total_est > line.product_uom_qty:
                line.est = line.product_uom_qty
            elif total_est <= 0:
                line.est = 0
            else:
                line.est = total_est
            
            _logger.info(f"Product: {line.product_id.name} | On Hand: {qty_on_hand_jadi} | Ready to Produce: {qty_ready_to_produce} | Final Est: {line.est}")


class EstSalesLineMo(models.Model):
    _inherit = 'sale.order.line'

    est = fields.Float(string="Estimasi Qty")