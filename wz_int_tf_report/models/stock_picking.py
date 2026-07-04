from odoo import api, fields, models, tools, _
import json
import requests

class StockPicking(models.Model):
    _inherit = "stock.picking"


    def action_print_internal_picking_report(self):
        return self.env.ref("wz_int_tf_report.internal_report_delivery").report_action(self)