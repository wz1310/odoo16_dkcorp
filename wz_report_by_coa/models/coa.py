# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, exceptions, api, _
from datetime import datetime
from odoo.exceptions import UserError, Warning


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

    def _is_valued_type_case(self):
        """
        Mengizinkan pembuatan Stock Valuation Layer / Jurnal untuk komponen 'service' di MO.
        """
        res = super(StockMove, self)._is_valued_type_case()
        if self.raw_material_production_id and self.product_id.type == 'service':
            return True
        return res

    def _get_src_account(self, account_data):
        """
        DITAMBAHKAN: Fallback akun kredit ke akun Expense / COGS milik produk servis,
        karena Product Category untuk service biasanya tidak memiliki Stock Valuation Account.
        """
        res = super(StockMove, self)._get_src_account(account_data)
        if self.product_id.type == 'service':
            expense_account = (
                self.product_id.property_account_expense_id 
                or self.product_id.categ_id.property_account_expense_categ_id
            )
            if expense_account:
                return expense_account.id
        return res

    def _get_price_unit(self):
        """
        DITAMBAHKAN: Memastikan unit price untuk pergerakan produk service
        mengambil nilai Cost (standard_price) dari master produk.
        """
        self.ensure_one()
        if self.product_id.type == 'service' and self.raw_material_production_id:
            return self.product_id.standard_price
        return super(StockMove, self)._get_price_unit()

    def _create_out_svl(self, forced_quantity=None):
        """
        Secara default Odoo melewati pembuat SVL jika produk bertipe 'service'.
        Kita override agar tetap dibuatkan SVL khusus jika move ini bagian dari MO.
        """
        svl_moves = super(StockMove, self)._create_out_svl(forced_quantity=forced_quantity)
        
        # Cari move bertipe service di MO yang belum dibuatkan SVL
        service_moves = self.filtered(
            lambda m: m.raw_material_production_id 
            and m.product_id.type == 'service' 
            and not m.stock_valuation_layer_ids
        )
        
        for move in service_moves:
            quantity = forced_quantity or move.product_uom_qty
            unit_cost = move.product_id.standard_price
            val_created = self.env['stock.valuation.layer'].create({
                'company_id': move.company_id.id,
                'product_id': move.product_id.id,
                'quantity': -quantity,
                'unit_cost': unit_cost,
                'value': -quantity * unit_cost,
                'remaining_qty': 0,
                'stock_move_id': move.id,
                'description': move.reference or move.origin,
            })
            # Buat entri jurnal akuntansi dari SVL yang baru dibuat
            val_created._validate_accounting_entries()
            
        return svl_moves


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_move_raw_values(self, product_id, qty, uom_id, operation_id=False, bom_line=False):
        """
        DITAMBAHKAN: Mengisikan nilai price_unit secara eksplisit saat dictionary move dibuat.
        """
        res = super(MrpProduction, self)._get_move_raw_values(product_id, qty, uom_id, operation_id, bom_line)
        if product_id.type == 'service':
            res['price_unit'] = product_id.standard_price
        return res

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