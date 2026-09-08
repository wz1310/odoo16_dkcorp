# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, exceptions, api, _
from datetime import datetime
from odoo.exceptions import UserError
from odoo.exceptions import Warning


class WzAccount(models.Model):

    _inherit = 'account.account'

    ycogs = fields.Boolean(string="YCOGS", default=False)
    ypnl = fields.Boolean(string="YPNL", default=False)
    ybs = fields.Boolean(string="YBS", default=False)
    mcogs = fields.Boolean(string="MCOGS", default=False)
    mpnl = fields.Boolean(string="MPNL", default=False)
    mbs = fields.Boolean(string="MBS", default=False)
    cogsvslmly = fields.Boolean(string="COGS VS LM LY", default=False)
    pnlvslmly = fields.Boolean(string="PNL VS LM LY", default=False)
    bslvslmly = fields.Boolean(string="BS VS LM LY", default=False)
    cogsytd = fields.Boolean(string="COGS YTD", default=False)
    pnlytd = fields.Boolean(string="PNL YTD", default=False)
    bsytd = fields.Boolean(string="BS YTD", default=False)

class StockMove(models.Model):
    _inherit = "stock.move"

    product_id = fields.Many2one(
        domain="[('type', 'in', ['product', 'consu', 'service']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    def _is_inventory_valuation_enabled(self):
        # Memaksa Odoo menganggap produk service pada MO butuh jurnal valuation
        self.ensure_one()
        if self.product_id.type == 'service' and self.raw_material_production_id:
            return self.product_id.valuation == 'real_time'
        return super()._is_inventory_valuation_enabled()

    def _get_accounting_data_for_valuation(self):
        # Memastikan akun debit/kredit diambil dari Product Category meski tipe produk Service
        journal_id, acc_src, acc_dest, acc_valuation = super()._get_accounting_data_for_valuation()
        if self.product_id.type == 'service' and self.raw_material_production_id:
            # Mengambil akun Expense/Interim sebagai akun sumber (Kredit)
            accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
            acc_src = accounts_data.get('expense') or accounts_data.get('stock_input')
        return journal_id, acc_src, acc_dest, acc_valuation

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_moves_raw_values(self):
        moves = []
        for production in self:
            if not production.bom_id:
                continue
            factor = production.product_uom_id._compute_quantity(
                production.product_qty, production.bom_id.product_uom_id
            ) / production.bom_id.product_qty
            
            boms, lines = production.bom_id.explode(
                production.product_id, 
                factor, 
                picking_type=production.bom_id.picking_type_id
            )
            
            for bom_line, line_data in lines:
                # KUSTOMISASI: Mengizinkan tipe 'service' selain 'product' dan 'consu'
                if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom' or \
                        bom_line.product_id.type not in ['product', 'consu', 'service']:
                    continue
                
                operation = bom_line.operation_id.id or (
                    line_data['parent_line'] and line_data['parent_line'].operation_id.id
                )
                
                moves.append(production._get_move_raw_values(
                    bom_line.product_id,
                    line_data['qty'],
                    bom_line.product_uom_id,
                    operation,
                    bom_line
                ))
        return moves