odoo.define('wz_notif_so.SoNotification', function (require) {
	'use strict';

	var rpc = require('web.rpc');
	var core = require('web.core');

	function ensureNotificationDOM() {
		if (!$('#global_so_floating_notif').length) {
			var htmlTemplate = `
				<div id="global_so_floating_notif" style="display: none; position: fixed; top: 60px; right: 20px; z-index: 99999; background-color: #e3f2fd; border: 1px solid #90caf9; padding: 12px 20px; border-radius: 6px; box-shadow: 0 4px 8px rgba(0,0,0,0.15); font-family: sans-serif; max-width: 320px;">
					<span class="o_so_close_btn" style="position: absolute; top: 4px; left: 8px; cursor: pointer; font-weight: bold; font-size: 12px; color: #555;" title="Tutup">✕</span>
					<div style="margin-top: 8px; font-size: 13px; color: #0d47a1; text-align: center;">
						Ada <span class="so-count-text" style="font-weight: bold;">0</span> jumlah so pending yang masih menunggu approval
					</div>
					<div style="text-align: center; margin-top: 8px;">
						<button type="button" class="o_so_redirect_btn btn btn-sm btn-primary" style="font-size: 11px; padding: 2px 8px; background-color: #1976d2; border-color: #1565c0; color: white;">Lihat List SO</button>
					</div>
				</div>
			`;
			$('body').append(htmlTemplate);
		}
	}

	var isClosedManually = false;
	var globalIntervalId = null;
	var lastKnownInterval = 0;

	function fetchAndRender() {
		ensureNotificationDOM();

		rpc.query({
			model: 'sale.order',
			method: 'get_pending_manager_approval_count',
		}).then(function (res) {
			var count = res.count || 0;
			var intervalMs = res.interval || 0;
			var $container =$('#global_so_floating_notif');

			if (intervalMs !== lastKnownInterval) {
				console.log("Interval updated from server:", intervalMs, "ms");
				lastKnownInterval = intervalMs;
				
				if (globalIntervalId) {
					clearInterval(globalIntervalId);
					globalIntervalId = null;
				}

				if (intervalMs > 0) {
					globalIntervalId = setInterval(fetchAndRender, intervalMs);
				}
			}

			if (intervalMs <= 0) {
				$container.fadeOut(500);
				return;
			}

			if (count > 0 && !isClosedManually) {
				$container.find('.so-count-text').text(count);
				$container.fadeIn(500); 		} else {$container.fadeOut(500);
			}

		}).catch(function (err) {
			console.error("RPC error fetching interval & pending SO count:", err);
		});
	}

	// Event listener untuk tombol close (X)
	$(document).on('click', '#global_so_floating_notif .o_so_close_btn', function (e) {
		e.stopPropagation();
		isClosedManually = true;
		$('#global_so_floating_notif').fadeOut(500);

		setTimeout(function () {
			isClosedManually = false;
		}, lastKnownInterval > 0 ? lastKnownInterval : 30000);
	});

	// Event listener untuk tombol redirect ke list SO menggunakan Action Dinamis dari Python
	$(document).on('click', '#global_so_floating_notif .o_so_redirect_btn', function (e) {
		e.preventDefault();
		console.log("Generating dynamic action for pending SO...");

		// Memanggil method Python untuk membuat action act_window dinamis dengan filter yang akurat
		rpc.query({
			model: 'sale.order',
			method: 'get_pending_manager_approval_action_id',
		}).then(function (actionId) {
			if (actionId) {
				console.log("Dynamic action created with ID:", actionId);
				window.location.href = '/web#action=' + actionId + '&view_type=list';
			} else {
				console.error("Failed to generate action ID.");
				window.location.href = '/web#model=sale.order&view_type=list';
			}
		}).catch(function (err) {
			console.error("RPC error generating dynamic action:", err);
			window.location.href = '/web#model=sale.order&view_type=list';
		});
	});

	// Jalankan pertama kali saat halaman siap
	$(document).ready(function () {
		setTimeout(function () {
			fetchAndRender();
		}, 1000);
	});

});