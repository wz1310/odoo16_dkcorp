# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import base64
import io
import xlsxwriter
from datetime import datetime
from dateutil.relativedelta import relativedelta


class FinancialReportCoaWizard(models.TransientModel):
    _name = 'financial.report.coa.wizard'
    _description = 'Financial Report by COA Wizard'

    date_from = fields.Date(string='Start Date', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='End Date', required=True, default=fields.Date.context_today)
    target_move = fields.Selection([
        ('posted', 'All Posted Entries'),
        ('all', 'All Entries'),
    ], string='Target Moves', required=True, default='posted')

    excel_file = fields.Binary('Download Report')
    filename = fields.Char('File Name')

    # =========================================================================
    # SQL QUERY METHODS UNTUK KINERJA TINGGI
    # =========================================================================

    def _get_pl_cogs_balances_sql(self, account_ids, date_from, date_to, group_by_type='year'):
        """
        Mengambil mutasi (Debit - Kredit) untuk PnL dan COGS (Tanpa akumulasi saldo awal).
        group_by_type: 'year' | 'month' | 'none'
        """
        if not account_ids:
            return {}

        params = [tuple(account_ids), date_from, date_to]
        state_clause = " AND am.state = 'posted' " if self.target_move == 'posted' else ""

        if group_by_type == 'year':
            select_group = ", EXTRACT(YEAR FROM aml.date)::INT AS grp_key"
            group_by_clause = ", EXTRACT(YEAR FROM aml.date)"
        elif group_by_type == 'month':
            select_group = ", EXTRACT(MONTH FROM aml.date)::INT AS grp_key"
            group_by_clause = ", EXTRACT(MONTH FROM aml.date)"
        else:
            select_group = ""
            group_by_clause = ""

        query = f"""
            SELECT 
                aml.account_id
                {select_group},
                SUM(
                    CASE 
                        WHEN acc.account_type IN ('income', 'income_other', 'liability_payable', 
                                                 'liability_credit_card', 'liability_current', 
                                                 'liability_non_current', 'equity', 'equity_unaffected')
                        THEN (aml.credit - aml.debit)
                        ELSE (aml.debit - aml.credit)
                    END
                ) AS balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account acc ON acc.id = aml.account_id
            WHERE aml.account_id IN %s
              AND aml.date >= %s
              AND aml.date <= %s
              {state_clause}
            GROUP BY aml.account_id {group_by_clause}
        """

        self.env.cr.execute(query, tuple(params))
        results = self.env.cr.dictfetchall()

        data_map = {}
        for row in results:
            key = (row['account_id'], row['grp_key']) if group_by_type != 'none' else row['account_id']
            data_map[key] = row['balance'] or 0.0

        return data_map

    def _get_bs_balances_sql(self, account_ids, date_to, year=None, month=None):
        """
        Mengambil posisi saldo Balance Sheet kumulatif dari awal waktu hingga date_to.
        """
        if not account_ids:
            return {}

        params = [tuple(account_ids), date_to]
        state_clause = " AND am.state = 'posted' " if self.target_move == 'posted' else ""

        query = f"""
            SELECT 
                aml.account_id,
                SUM(
                    CASE 
                        WHEN acc.account_type IN ('income', 'income_other', 'liability_payable', 
                                                 'liability_credit_card', 'liability_current', 
                                                 'liability_non_current', 'equity', 'equity_unaffected')
                        THEN (aml.credit - aml.debit)
                        ELSE (aml.debit - aml.credit)
                    END
                ) AS balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account acc ON acc.id = aml.account_id
            WHERE aml.account_id IN %s
              AND aml.date <= %s
              {state_clause}
            GROUP BY aml.account_id
        """

        self.env.cr.execute(query, tuple(params))
        results = self.env.cr.dictfetchall()

        data_map = {}
        for row in results:
            if year and month:
                key = (row['account_id'], month)
            elif year:
                key = (row['account_id'], year)
            else:
                key = row['account_id']
            data_map[key] = row['balance'] or 0.0

        return data_map

    # =========================================================================
    # GENERATE REPORT
    # =========================================================================

    def generate_excel_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formats
        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        num_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        bold_num_format = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'border': 1})
        text_format = workbook.add_format({'border': 1})

        dt_from = self.date_from
        dt_to = self.date_to

        start_year = dt_from.year
        end_year = dt_to.year
        years = list(range(start_year, end_year + 1))

        sheet_configs = [
            {'code': 'ycogs', 'name': 'YCOGS', 'title': 'YEARLY COST OF GOODS SOLD', 'type': 'yearly', 'is_bs': False},
            {'code': 'ypnl', 'name': 'YPNL', 'title': 'YEARLY PROFIT AND LOSS', 'type': 'yearly', 'is_bs': False},
            {'code': 'ybs', 'name': 'YBS', 'title': 'YEARLY BALANCE SHEET', 'type': 'yearly', 'is_bs': True},
            {'code': 'mcogs', 'name': 'MCOGS', 'title': 'MONTHLY COST OF GOODS SOLD', 'type': 'monthly', 'is_bs': False},
            {'code': 'mpnl', 'name': 'MPNL', 'title': 'MONTHLY PROFIT AND LOSS', 'type': 'monthly', 'is_bs': False},
            {'code': 'mbs', 'name': 'MBS', 'title': 'MONTHLY BALANCE SHEET', 'type': 'monthly', 'is_bs': True},
            {'code': 'cogsvslmly', 'name': 'COGS VS LM LY', 'title': 'COST OF GOODS SOLD VS LM LY', 'type': 'vslmly', 'is_bs': False},
            {'code': 'pnlvslmly', 'name': 'PNL VS LM LY', 'title': 'PROFIT AND LOSS VS LM LY', 'type': 'vslmly', 'is_bs': False},
            {'code': 'bslvslmly', 'name': 'BS VS LM LY', 'title': 'BALANCE SHEET VS LM LY', 'type': 'vslmly', 'is_bs': True},
            {'code': 'cogsytd', 'name': 'COGS YTD', 'title': 'COST OF GOODS SOLD YTD', 'type': 'ytd', 'is_bs': False},
            {'code': 'pnlytd', 'name': 'PNL YTD', 'title': 'PROFIT AND LOSS YTD', 'type': 'ytd', 'is_bs': False},
            {'code': 'bsytd', 'name': 'BS YTD', 'title': 'BALANCE SHEET YTD', 'type': 'ytd', 'is_bs': True},
        ]

        for cfg in sheet_configs:
            worksheet = workbook.add_worksheet(cfg['name'])
            worksheet.write(1, 0, cfg['title'], title_format)

            accounts = self.env['account.account'].search([
                (cfg['code'], '=', True)
            ], order='code asc')
            account_ids = accounts.ids

            is_bs = cfg['is_bs']

            # --- 1. YEARLY REPORTS (YCOGS, YPNL, YBS) ---
            if cfg['type'] == 'yearly':
                headers = ['Kode Akun', 'Nama Akun'] + [str(y) for y in years]
                if not is_bs:
                    headers.append('TOTAL')

                for col_num, h in enumerate(headers):
                    worksheet.write(4, col_num, h, header_format)

                # Fetch Data via SQL
                if is_bs:
                    data_map = {}
                    for y in years:
                        y_to = f"{y}-12-31"
                        sub_map = self._get_bs_balances_sql(account_ids, y_to, year=y)
                        data_map.update(sub_map)
                else:
                    data_map = self._get_pl_cogs_balances_sql(account_ids, dt_from, dt_to, group_by_type='year')

                row = 5
                for acc in accounts:
                    worksheet.write(row, 0, acc.code or '', text_format)
                    worksheet.write(row, 1, acc.name or '', text_format)
                    total_val = 0.0
                    col = 2
                    for y in years:
                        val = data_map.get((acc.id, y), 0.0)
                        worksheet.write(row, col, val, num_format)
                        total_val += val
                        col += 1
                    if not is_bs:
                        worksheet.write(row, col, total_val, bold_num_format)
                    row += 1

            # --- 2. MONTHLY REPORTS (MCOGS, MPNL, MBS) ---
            elif cfg['type'] == 'monthly':
                months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                headers = ['Kode Akun', 'Nama Akun'] + months
                for col_num, h in enumerate(headers):
                    worksheet.write(4, col_num, h, header_format)

                target_year = dt_to.year

                if is_bs:
                    data_map = {}
                    for m in range(1, 13):
                        m_to = (datetime(target_year, m, 1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')
                        sub_map = self._get_bs_balances_sql(account_ids, m_to, year=target_year, month=m)
                        data_map.update(sub_map)
                else:
                    m_start = f"{target_year}-01-01"
                    m_end = f"{target_year}-12-31"
                    data_map = self._get_pl_cogs_balances_sql(account_ids, m_start, m_end, group_by_type='month')

                row = 5
                for acc in accounts:
                    worksheet.write(row, 0, acc.code or '', text_format)
                    worksheet.write(row, 1, acc.name or '', text_format)
                    for m in range(1, 13):
                        val = data_map.get((acc.id, m), 0.0)
                        worksheet.write(row, m + 1, val, num_format)
                    row += 1

            # --- 3. COMPARISON REPORTS (VS LM LY) ---
            elif cfg['type'] == 'vslmly':
                headers = ['Kode Akun', 'Nama Akun', 'THIS MONTH', 'LM', 'LY', '%LM', '%LY']
                for col_num, h in enumerate(headers):
                    worksheet.write(4, col_num, h, header_format)

                lm_from = dt_from - relativedelta(months=1)
                lm_to = dt_to - relativedelta(months=1)
                ly_from = dt_from - relativedelta(years=1)
                ly_to = dt_to - relativedelta(years=1)

                if is_bs:
                    tm_data = self._get_bs_balances_sql(account_ids, dt_to)
                    lm_data = self._get_bs_balances_sql(account_ids, lm_to)
                    ly_data = self._get_bs_balances_sql(account_ids, ly_to)
                else:
                    tm_data = self._get_pl_cogs_balances_sql(account_ids, dt_from, dt_to, group_by_type='none')
                    lm_data = self._get_pl_cogs_balances_sql(account_ids, lm_from, lm_to, group_by_type='none')
                    ly_data = self._get_pl_cogs_balances_sql(account_ids, ly_from, ly_to, group_by_type='none')

                row = 5
                for acc in accounts:
                    tm_val = tm_data.get(acc.id, 0.0)
                    lm_val = lm_data.get(acc.id, 0.0)
                    ly_val = ly_data.get(acc.id, 0.0)

                    pct_lm = ((tm_val - lm_val) / lm_val * 100) if lm_val else 0.0
                    pct_ly = ((tm_val - ly_val) / ly_val * 100) if ly_val else 0.0

                    worksheet.write(row, 0, acc.code or '', text_format)
                    worksheet.write(row, 1, acc.name or '', text_format)
                    worksheet.write(row, 2, tm_val, num_format)
                    worksheet.write(row, 3, lm_val, num_format)
                    worksheet.write(row, 4, ly_val, num_format)
                    worksheet.write(row, 5, pct_lm, num_format)
                    worksheet.write(row, 6, pct_ly, num_format)
                    row += 1

            # --- 4. YTD REPORTS ---
            elif cfg['type'] == 'ytd':
                headers = ['Kode Akun', 'Nama Akun', 'THIS MONTH', 'YTD']
                for col_num, h in enumerate(headers):
                    worksheet.write(4, col_num, h, header_format)

                ytd_from = dt_to.replace(month=1, day=1)

                if is_bs:
                    tm_data = self._get_bs_balances_sql(account_ids, dt_to)
                    ytd_data = self._get_bs_balances_sql(account_ids, dt_to)
                else:
                    tm_data = self._get_pl_cogs_balances_sql(account_ids, dt_from, dt_to, group_by_type='none')
                    ytd_data = self._get_pl_cogs_balances_sql(account_ids, ytd_from, dt_to, group_by_type='none')

                row = 5
                for acc in accounts:
                    tm_val = tm_data.get(acc.id, 0.0)
                    ytd_val = ytd_data.get(acc.id, 0.0)

                    worksheet.write(row, 0, acc.code or '', text_format)
                    worksheet.write(row, 1, acc.name or '', text_format)
                    worksheet.write(row, 2, tm_val, num_format)
                    worksheet.write(row, 3, ytd_val, num_format)
                    row += 1

        workbook.close()
        output.seek(0)

        file_bytes = base64.b64encode(output.read())
        filename = f"LAPORAN_KEUANGAN_{dt_from}_TO_{dt_to}.xlsx"

        self.write({
            'excel_file': file_bytes,
            'filename': filename
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&download=true&filename={self.filename}',
            'target': 'self',
        }