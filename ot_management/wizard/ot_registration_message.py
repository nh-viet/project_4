# -*- coding: utf-8 -*-

from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import api, models, fields


class OTApproveRemindMessage(models.TransientModel):
    _name = "ot.remind.message"
    _description = "OT Remind Message"

    emails = fields.Char('Email List')
    month = fields.Char('Month')

    def check_ot_waiting_to_approve(self):
        manager_list = self.env['ot.registration'].search([('state', '=', 'to_approve')]).mapped('manager_id')
        dl_list = self.env['ot.registration'].search([('state', '=', 'approved')]).mapped('dl_manager_id')
        emails = ', '.join(manager_id.work_email for manager_id in set(manager_list + dl_list))
        created_id = self.create({'emails': emails, 'month': datetime.now().strftime('%B, %Y')})
        created_id.send_mail_remind_approve_ot()
        return True

    def send_mail_remind_approve_ot(self):
        self.ensure_one()
        template = self.env.ref('vti_ot_registration.ot_remind_approve_mail_template')
        mail_template = self.env['mail.template'].browse(template.id)
        mail_template.send_mail(self.id)

    @api.multi
    def get_ot_link(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        link = base_url + "/overtime/to_approve/"
        return link


class OTRegistrationMessage(models.TransientModel):
    _name = "ot.registration.message"
    _description = "OT Registration Message"

    def _get_default_message(self):
        if self._context.get('type', False) == 'hr_refuse_line':
            return ''
        active_ids = self._context.get('active_ids', False)
        ot_ids = self.env['ot.registration'].browse(active_ids)
        return ot_ids.get_ot_message() or ''

    def _get_default_message_to(self):
        type = self._context.get('type', False)
        if type == 'submit':
            return "Tôi đã hiểu và cam kết đăng kí đúng theo quy định."
        elif type in ['pm_approve', 'dl_approve']:
            return "Tôi xem và chấp thuận với yêu cầu đăng ký làm thêm này."

    message = fields.Text(string="Message", default=_get_default_message)
    message_to = fields.Text(string="Hr Note", default=_get_default_message_to)
    notes = fields.Text(string="Hr Note")

    def do_submit_ot(self):
        self.ensure_one()
        active_ids = self._context.get('active_ids', False)
        type = self._context.get('type', False)
        ot_ids = self.env['ot.registration'].browse(active_ids)
        if type == 'submit':
            ot_ids.submit_request()
        elif type == 'pm_approve':
            ot_ids.approve_request()
        elif type == 'dl_approve':
            ot_ids.done_request()
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def hr_refuse_request(self):
        active_id = self._context.get('active_id', False)
        ot_line_id = self.env['ot.registration.lines'].browse(active_id)
        if ot_line_id:
            ot_line_id.write({'state': 'refused', 'approve_date': False, 'notes': self.notes})
            if ot_line_id.ot_registration_id and not ot_line_id.ot_registration_id.ot_lines and \
                    ot_line_id.ot_registration_id.leaves_id:
                ot_line_id.ot_registration_id.leaves_id.state = 'draft'
                ot_line_id.ot_registration_id.leaves_id.unlink()
                ot_line_id.ot_registration_id.write({'state': 'refused', 'approve_date': False,
                                                     'notes': 'OT refused by HR manager!'})
            else:
                ot_line_id.ot_registration_id.update_allocation_time()
            ot_line_id.send_mail_refuse_ot_to_emp()
