import datetime
from odoo import models


class InternalReportDeliveryXlsx(models.AbstractModel):
    _name = 'report.wz_int_tf_report.report_delivery_internal_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Internal Delivery Report XLSX'

    def generate_xlsx_report(self, workbook, data, pickings):
        for o in pickings:
            sheet = workbook.add_worksheet(o.name[:31] if o.name else 'Internal Transfer')
            
            # --- Styles & Formats ---
            title_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 14, 'bold': True
            })
            header_right_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 14, 'bold': True, 'align': 'right'
            })
            bold_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 10, 'bold': True
            })
            normal_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 10
            })
            right_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 10, 'align': 'right'
            })
            center_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 10, 'align': 'center'
            })
            
            # Table Header Format (Border Atas-Bawah Putus-Putus / Dashed)
            th_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 11, 'bold': True, 'align': 'center', 'valign': 'vcenter',
                'top': 2, 'bottom': 2  # 2 represents dashed border in xlsxwriter
            })
            
            # Numeric Format (2 Decimals)
            num_format = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 10, 'align': 'center', 'num_format': '#,##0.00'
            })
            
            # Border Bottom Line Format (Dashed)
            bottom_dashed = workbook.add_format({
                'top': 2
            })
            
            small_right = workbook.add_format({
                'font_name': 'Tahoma', 'font_size': 9, 'align': 'right', 'italic': True
            })

            # --- Column Widths ---
            sheet.set_column('A:A', 6)    # No
            sheet.set_column('B:B', 35)   # Nama Barang
            sheet.set_column('C:C', 14)   # Jumlah
            sheet.set_column('D:D', 12)   # Satuan
            sheet.set_column('E:E', 25)   # Keterangan

            # --- Header Information ---
            sheet.write('A1', o.company_id.name or '', title_format)
            sheet.merge_range('C1:E1', 'INTERNAL TRANSFER', header_right_format)

            sheet.write('A2', f"Source Location: {o.location_id.display_name or ''}", normal_format)
            sheet.write('C2', 'No Internal Transfer', right_format)
            sheet.write('D2', ':', center_format)
            sheet.write('E2', o.name or '', normal_format)

            sheet.write('A3', f"Destination Location: {o.location_dest_id.display_name or ''}", normal_format)
            sheet.write('C3', 'Tgl Internal Transfer', right_format)
            sheet.write('D3', ':', center_format)
            sched_date = o.scheduled_date.strftime('%d %B %Y') if o.scheduled_date else ''
            sheet.write('E3', sched_date, normal_format)

            sheet.write('A4', o.partner_id.street or '', normal_format)
            sheet.write('C4', 'No. Order', right_format)
            sheet.write('D4', ':', center_format)
            sheet.write('E4', o.origin or '', normal_format)

            sheet.write('C5', 'No. PO', right_format)
            sheet.write('D5', ':', center_format)
            sheet.write('E5', o.po_number or '', normal_format)

            # --- Table Column Titles (Row 7, Index 6) ---
            sheet.write(6, 0, 'No', th_format)
            sheet.write(6, 1, 'Nama Barang', th_format)
            sheet.write(6, 2, 'Jumlah', th_format)
            sheet.write(6, 3, 'Satuan', th_format)
            sheet.write(6, 4, 'Keterangan', th_format)

            # --- Table Data (Move Lines) ---
            row = 7
            i = 1
            qty_total = 0.0

            for move in o.move_ids:
                sheet.write(row, 0, i, right_format)
                sheet.write(row, 1, move.product_id.name or '', normal_format)
                sheet.write(row, 2, move.product_uom_qty or 0.0, num_format)
                sheet.write(row, 3, move.product_uom.name or '', center_format)
                sheet.write(row, 4, move.move_remark or '', normal_format)
                
                qty_total += move.product_uom_qty
                i += 1
                row += 1

            # Bottom dashed line after table data
            for col in range(5):
                sheet.write_blank(row, col, '', bottom_dashed)
            row += 1

            # --- Total & Summary Section ---
            sheet.write(row, 1, f"Item : {i - 1}", normal_format)
            sheet.write(row, 2, f"Total Quantity : {qty_total:,.2f}", normal_format)
            row += 2

            # --- Signatures Section ---
            sheet.write(row, 0, 'Mengetahui,', normal_format)
            row += 1
            sheet.write(row, 0, 'Pengirim :', normal_format)
            sheet.write(row, 1, 'Driver :', normal_format)
            sheet.write(row, 2, 'Penerima :', normal_format)
            row += 3

            # --- Footer (User & Timestamp WIB / GMT+7) ---
            user_name = o.user_id.name if o.user_id else (o.write_uid.name or '')
            now = datetime.datetime.now() + datetime.timedelta(hours=7)
            time_str = now.strftime('%d/%m/%Y %H:%M:%S')
            created_by_str = f"Dibuat: {user_name} | {time_str}"
            
            sheet.merge_range(row, 0, row, 4, created_by_str, small_right)