# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, exceptions, api, _
from datetime import datetime
from odoo.exceptions import UserError
from odoo.exceptions import Warning

class InheritConfirmDateWizard(models.TransientModel):
    _inherit = 'confirmation.date.wizard'
   
    def action_confirm(self):
        context = dict(self._context) or {}
        if context.get('active_id', False):
            sale_obj = self.env['sale.order'].browse(context.get('active_id'))
            sale_obj.action_confirm()
            if self.confirmation_force_date:
                if self.confirmation_force_date.date() >= datetime.now().date():
                    raise UserError(_('Please Enter Correct Back Date'))
                sale_obj.date_order = self.confirmation_force_date
            picking = self.env['stock.picking'].search([('sale_id', '=', sale_obj.id), ('state', 'not in', ['cancel'])])
            if picking:
                picking.partner_id = sale_obj.partner_id.id
            if not sale_obj.commitment_date:
                for pic in picking:
                    if self.confirmation_force_date:
                        picking.scheduled_date = self.confirmation_force_date

        return True
            
    def skip_backdate(self):
        context = dict(self._context) or {}
        if context.get('active_id', False):
            sale_obj = self.env['sale.order'].browse(context.get('active_id'))
            sale_obj.action_confirm() 
            picking = self.env['stock.picking'].search([('sale_id', '=', sale_obj.id), ('state', 'not in', ['cancel'])])
            if picking:
                picking.partner_id = sale_obj.partner_id.id