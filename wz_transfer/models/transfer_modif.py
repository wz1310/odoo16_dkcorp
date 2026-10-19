# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import float_round

import logging
_logger = logging.getLogger(__name__)

class SalesInherit(models.Model):
    _inherit = 'sale.order'

    driver_pengganti = fields.Many2one('res.users',string="Driver Pengganti")
    send_by = fields.Selection(
        [('grab', 'Grab'),
         ('gojek', 'Gojek'),
         ('lala_move', 'Lala Move'),
         ('si_cepat', 'Sicepat'),
         ('jnt', 'JNT'),
         ('jne', 'JNE'),
         ('lainnya', 'Lainnya'),
         ],
        string='Opsi Pengiriman')



class PickInherit(models.Model):
    _inherit = 'stock.picking'

    send_by_so = fields.Selection(
        [('grab', 'Grab'),
         ('gojek', 'Gojek'),
         ('lala_move', 'Lala Move'),
         ('si_cepat', 'Sicepat'),
         ('jnt', 'JNT'),
         ('jne', 'JNE'),
         ('lainnya', 'Lainnya'),
         ],
        string='Opsi Pengiriman')

