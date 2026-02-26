import json
import datetime
import math
import re

from ast import literal_eval
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.tools.misc import OrderedSet, format_date, groupby as tools_groupby

from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES


class MrpProduction(models.Model):

    _inherit = 'mrp.production'

    # automate = fields.Boolean()


    # def action_auto_qty_consume(self):
    #     print("jalan Auto Consume", fields.Date.today())
    #     mo_confirm = self.search([('state','=','confirmed'),('automate','=',False),('create_date','>=',fields.Date.today())])
    #     for x in mo_confirm:
    #         x.qty_producing = x.product_qty
    #         x._onchange_producing()
    #         x.automate = True

    def action_confirm(self):
        res = super(MrpProduction, self).action_confirm()

        confirmed_mos = self.filtered(lambda x: x.state == 'confirmed')
        if not confirmed_mos:
            return res
        cr = self.env.cr
        mo_ids = tuple(confirmed_mos.ids)
        # print("11111111111111111111111111111111")
        cr.execute("""UPDATE mrp_production SET qty_producing = product_qty WHERE id IN %s;
            UPDATE stock_move SET quantity_done = product_uom_qty
            WHERE raw_material_production_id IN %s AND state NOT IN ('done', 'cancel');
            """, (mo_ids, mo_ids))

        # print("2222222222222222222222222")
        cr.execute("""
            UPDATE stock_move_line
            SET qty_done = reserved_uom_qty
            WHERE production_id IN %s
            AND state NOT IN ('done', 'cancel');
            """, (mo_ids,))

        # print("33333333333333333333333")
        cr.execute("""
            INSERT INTO stock_move_line (
            move_id, product_id, product_uom_id,
            qty_done, reserved_uom_qty,
            location_id, location_dest_id, company_id,
            state, production_id, reference, date, create_date, write_date,
            create_uid, write_uid)
            SELECT
            m.id, m.product_id, m.product_uom,
            m.product_uom_qty, 0,
            m.location_id, m.location_dest_id, m.company_id,
            'confirmed', m.raw_material_production_id, m.reference, NOW(), NOW(), NOW(),
            %s, %s
            FROM stock_move m
            LEFT JOIN stock_move_line ml ON m.id = ml.move_id
            WHERE m.raw_material_production_id IN %s
            AND m.state NOT IN ('done', 'cancel')
            AND ml.id IS NULL
            """, (self.env.uid, self.env.uid, mo_ids))
        return res