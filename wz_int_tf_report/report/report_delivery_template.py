import time
from odoo import api, models, _
from odoo.exceptions import UserError
import datetime

class InternalReportDelivery(models.AbstractModel):
    _name = 'wz_int_tf_report.report_delivery_internal'
    _description = 'Internal Delivery Report'

    def _get_report_values(self, docids, data=None):
        stock_picking = self.env['stock.picking'].browse(docids[0])
        return {
            'doc_model': 'stock.picking',
            'docs': stock_picking,
            'date': datetime.datetime.now()
        }