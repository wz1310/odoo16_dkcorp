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