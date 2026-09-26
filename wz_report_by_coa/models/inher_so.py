# -*- coding: utf-8 -*-
import math
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.exceptions import ValidationError


class SaleOrderWorkerLine(models.Model):
    _name = 'sale.order.worker.line'
    _description = 'Detail Pekerja Sales Order'

    order_id = fields.Many2one('sale.order', string='Sales Order', ondelete='cascade')
    worker_id = fields.Many2one('mrp.worker', string='Pekerja', required=True)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    worker_line_ids = fields.One2many(
        'sale.order.worker.line', 
        'order_id', 
        string='Daftar Pekerja'
    )
    batch_id = fields.Many2one('sale.order.batch', string='Batch')

class SaleOrderBatch(models.Model):
    _name = 'sale.order.batch'
    _description = 'Master Batch Sales Order'

    name = fields.Char(string='Nama Batch', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Field One2many untuk merekam Sales Order yang terhubung ke Batch ini
    sale_order_ids = fields.One2many(
        'sale.order', 
        'batch_id', 
        string='Sales Order'
    )