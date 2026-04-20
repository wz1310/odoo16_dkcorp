# models/product_image_custom.py
from odoo import models, fields, _
from odoo.exceptions import UserError

class ProductImageCustom(models.Model):
    _name = 'product.image.custom'
    _description = 'Custom Product Images'

    name = fields.Char(string="Nama File")
    image_1920 = fields.Image(string="Gambar", required=True)
    # Field relasi ke product.template
    product_tmpl_id = fields.Many2one('product.template', string="Produk", ondelete='cascade')
    do_img_id = fields.Many2one('stock.picking', string="Stock", ondelete='cascade')

    def action_download_image(self):
    	self.ensure_one()
    	return {
    	'type': 'ir.actions.act_url',
    	'url': f'/web/content/?model={self._name}&id={self.id}&field=image_1920&filename_field=name&download=true',
    	'target': 'self',
    	}

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Gunakan model kustom kita di sini
    multi_upload_images = fields.One2many(
        'product.image.custom', 
        'product_tmpl_id', 
        string="Daftar Gambar Kustom"
    )

class DoImage(models.Model):
    _inherit = 'stock.picking'

    # Gunakan model kustom kita di sini
    multi_upload_images = fields.One2many(
        'product.image.custom',
        'do_img_id', 
        string="Daftar Gambar Kustom"
    )
    # state = fields.Selection(selection_add=[('received', 'Received')])
    delivery_state = fields.Selection([
        ('confirmed', 'Waiting'),
        ('received', 'Received')
    ],ondelete='cascade', default='confirmed',track_visibility="onchange")

    def receive_do(self):
        if len(self.multi_upload_images.ids) > 0:
            self.delivery_state = 'received'
        else:
            raise UserError(_("Upload photo terlebih dahulu"))