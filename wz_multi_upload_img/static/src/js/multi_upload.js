/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { useService } from "@web/core/utils/hooks";
import { useRef } from "@odoo/owl";

export class MultiImageUpload extends X2ManyField {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.fileInput = useRef("fileInput");
    }

    async readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async onFileInputChange(ev) {
        const files = Array.from(ev.target.files);
        if (files.length === 0) return;

        const record = this.props.record;
        const root = record.model.root;
        const resId = record.resId;
        let successCount = 0;

        try {
            // 🔥 CARA AMAN MASUK MODE EDIT DI ODOO 16
            if (root.mode !== "edit") {
                if (typeof root.switchMode === "function") {
                    await root.switchMode("edit");
                }
            }

            for (const file of files) {
                try {
                    const base64Data = await this.readFile(file);
                    
                    await this.orm.create("product.image.custom", [{
                        name: file.name,
                        image_1920: base64Data,
                        product_tmpl_id: resId,
                    }]);

                    successCount++;
                } catch (error) {
                    console.error(`Gagal upload: ${file.name}`, error);
                }
            }

            if (successCount > 0) {
                // 🔥 SINKRONISASI DATA
                // 1. Ambil data terbaru dari server
                await record.load();
                
                // 2. Beritahu list model bahwa data telah berubah
                if (this.list) {
                    await this.list.model.root.update();
                }

                // 3. Paksa render ulang UI widget
                this.render();

                this.notification.add(`${successCount} gambar berhasil ditambahkan.`, {
                    type: "success",
                });
            }
        } catch (err) {
            console.error("Gagal melakukan refresh UI:", err);
            // Fallback jika switchMode gagal, tetap coba jalankan load
            await record.load();
        }

        ev.target.value = "";
    }

    onButtonClick() {
        if (!this.props.record.resId) {
            this.notification.add("Simpan produk terlebih dahulu.", { type: "warning" });
            return;
        }
        this.fileInput.el?.click();
    }
}

MultiImageUpload.template = "wz_multi_upload_img.MultiImageUpload";
registry.category("fields").add("multi_image", MultiImageUpload);