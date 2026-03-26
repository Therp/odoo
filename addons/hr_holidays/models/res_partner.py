# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _compute_im_status(self):
        super(ResPartner, self)._compute_im_status()
        absent_now = self._get_on_leave_ids()
        # see what super did to cache
        base_status_by_id = {
            partner.id: partner._cache.get('im_status') or 'offline'
            for partner in self
        }
        for partner in self:
            # fetch the cached value for recomputing
            base_status = base_status_by_id[partner.id]
            if partner.id in absent_now:
                partner.im_status = 'leave_online' if base_status == 'online' else 'leave_offline'
            else:
                partner.im_status = base_status

    @api.model
    def _get_on_leave_ids(self):
        return self.env['res.users']._get_on_leave_ids(partner=True)
