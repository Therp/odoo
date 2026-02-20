from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpGenerateSerials(models.TransientModel):
    _name = "mrp.generate.serials"
    _description = "Pregenerate serial numbers for a Mass MO"

    production_id = fields.Many2one("mrp.production", required=True, readonly=True)
    first_lot_sn = fields.Char(string="First Serial")
    qty = fields.Integer(string="Number of Serials", required=True, default=1)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if not active_id:
            raise UserError(_("Open this wizard from a Manufacturing Order."))
        mo = self.env["mrp.production"].browse(active_id)
        vals["production_id"] = mo.id
      	# guess this if possible
        vals["first_lot_sn"] = self.env["stock.lot"]._get_next_serial(mo.company_id, mo.product_id)
        vals["qty"] = max(int(mo.product_qty) - len(mo.lot_ids), 1)
        return vals

    def action_generate(self):
        self.ensure_one()
        mo = self.production_id
        if mo.product_tracking != "serial":
            raise UserError(_("The product is not tracked by unique serial number."))
        if self.qty <= 0:
            raise UserError(_("Please enter a number of serials to generate."))
        if not self.first_lot_sn:
            raise UserError(_("Please specify the first serial number."))
        lots_name = self.env["stock.lot"].generate_lot_names(self.first_lot_sn, self.qty)
        names = [x["lot_name"] for x in lots_name]
        existing = self.env["stock.lot"].search([
            ("company_id", "in", [mo.company_id.id, False]),
            ("product_id", "=", mo.product_id.id),
            ("name", "in", names),
        ])
        existing_names = set(existing.mapped("name"))
        to_create = [{"name": n, "product_id": mo.product_id.id} for n in names if n not in existing_names]
        created = self.env["stock.lot"].create(to_create) if to_create else self.env["stock.lot"]
        lots = existing | created
        lots_by_name = {l.name: l.id for l in lots}
        ordered_ids = [lots_by_name[n] for n in names if n in lots_by_name]
        mo.lot_ids = [(6, 0, ordered_ids)]
        return {"type": "ir.actions.act_window_close"}
