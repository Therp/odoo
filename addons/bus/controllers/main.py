# -*- coding: utf-8 -*-

import logging
import os

from odoo import exceptions, _
from odoo.http import Controller, request, route
from odoo.addons.bus.models.bus import dispatch

_logger = logging.getLogger(__name__)


class BusController(Controller):
    """ Examples:
    openerp.jsonRpc('/longpolling/poll','call',{"channels":["c1"],last:0}).then(function(r){console.log(r)});
    openerp.jsonRpc('/longpolling/send','call',{"channel":"c1","message":"m1"});
    openerp.jsonRpc('/longpolling/send','call',{"channel":"c2","message":"m2"});
    """

    @route('/longpolling/send', type="json", auth="public")
    def send(self, channel, message):
        if not isinstance(channel, str):
            raise Exception("bus.Bus only string channels are allowed.")
        return request.env['bus.bus'].sendone(channel, message)

    # override to add channels
    def _poll(self, dbname, channels, last, options):
        # update the user presence
        if request.session.uid and 'bus_inactivity' in options:
            request.env['bus.presence'].update(options.get('bus_inactivity'))
        request.cr.close()
        request._cr = None
        return dispatch.poll(dbname, channels, last, options)

    @route('/longpolling/poll', type="json", auth="public", cors="*")
    def poll(self, channels, last, options=None):
        if options is None:
            options = {}
        if not dispatch:
            raise Exception("bus.Bus unavailable")
        if [c for c in channels if not isinstance(c, str)]:
            raise Exception("bus.Bus only string channels are allowed.")
        if request.registry.in_test_mode():
            raise exceptions.UserError(_("bus.Bus not available in test mode"))
        return self._poll(request.db, channels, last, options)

    @route('/longpolling/im_status', type="json", auth="user")
    def im_status(self, partner_ids):
        Partner = request.env['res.partner'].with_context(active_test=False)
        current_user = request.env.user
        try:
            return Partner.search([('id', 'in', partner_ids)]).read(['im_status'])
        except ValueError as err:
            _logger.exception(
                "IM STATUS batch failure: user_id=%s login=%s user_partner_id=%s "
                "partner_ids=%s db=%s pid=%s context=%s error=%r",
                current_user.id,
                current_user.login,
                current_user.partner_id.id,
                partner_ids,
                request.db,
                os.getpid(),
                dict(request.env.context),
                err,
            )
            failing_ids = []
            successful_rows = []
            for partner_id in partner_ids:
                try:
                    row = Partner.browse(partner_id).read(['im_status'])[0]
                    successful_rows.append(row)
                except Exception:
                    failing_ids.append(partner_id)
                    _logger.exception(
                        "IM STATUS single failure: user_id=%s login=%s "
                        "user_partner_id=%s failing_partner_id=%s db=%s pid=%s",
                        current_user.id,
                        current_user.login,
                        current_user.partner_id.id,
                        partner_id,
                        request.db,
                        os.getpid(),
                    )
            if failing_ids:
                _logger.warning(
                    "IM STATUS fallback applied: failing_ids=%s successful_rows=%s",
                    failing_ids,
                    successful_rows,
                )
            return successful_rows + [{'id': pid, 'im_status': 'offline'} for pid in failing_ids]
