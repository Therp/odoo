# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _compute_im_status(self):
        _logger.warning("PARTNER IM STATUS START ids=%s", self.ids)
        super(ResPartner, self)._compute_im_status()
        absent_now = set(self._get_on_leave_ids())
        # see what super did to cache
        base_status_by_id = {
            partner.id: partner._cache.get('im_status') or 'offline'
            for partner in self
        }
        for partner in self:
            base_status = base_status_by_id[partner.id]

            if partner.id in absent_now:
                final_status = (
                    'leave_online'
                    if base_status == 'online'
                    else 'leave_offline'
                )
            else:
                final_status = base_status
            _logger.warning(
                "PARTNER IM STATUS partner=%s base=%s on_leave=%s final=%s",
                partner.id,
                base_status,
                partner.id in absent_now,
                final_status,
            )
            partner.im_status = final_status

    @api.model
    def _get_on_leave_ids(self):
        return self.env['res.users']._get_on_leave_ids(partner=True)
