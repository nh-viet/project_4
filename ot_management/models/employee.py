from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import ValidationError, UserError


class EmployeeOt(models.Model):
    _name = 'res.ot'
    _inherit = 'mail.thread'

    def _get_employee_id(self):
        employee_rec = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee_rec.id

    def _get_manager_id(self):
        manager_rec = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if manager_rec.parent_id:
            return manager_rec.parent_id
        else:
            return manager_rec.id

    name = fields.Char(string='Name', related='employee_id.name')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('pm_approved', 'PM Approved'),
        ('dl_approved', 'DL Approved'),
        ('pm_refused', 'Refused'),
        ('dl_refused', 'Refused')
    ], default='draft')
    res_ot_line_ids = fields.One2many('res.ot.line', 'employee_ot_id', string='Res Ot Line Ids')
    user_id = fields.Many2one('res.users', string='User Id', default=lambda self: self.env.user, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', default=_get_employee_id, readonly=True)
    department_id = fields.Char(string='Department Id', related='employee_id.department_id.name')
    department_lead_id = fields.Many2one('hr.employee', string='Department Lead', default=_get_manager_id,
                                         readonly=True)
    project_id = fields.Many2one('project.project', string='Project', required=True)
    line_total_ot = fields.Integer(string='Total OT', compute='_compute_line_total_ot', compute_sudo=True, store=True
                                   , group_operator="sum")
    line_ot_month = fields.Char(string='OT Month', compute='_compute_ot_month', compute_sudo=True)
    approver = fields.Char(string='Approver', related='project_id.user_id.name')
    hide_edit_button = fields.Html(string='Hide Edit Button', sanitize=False, compute='_compute_hide_edit_button',
                                   compute_sudo=True)
    hide_delete_button = fields.Html(string='Hide Delete Button', sanitize=False, compute='_compute_hide_delete_button',
                                     compute_sudo=True)

    def send_email(self, string):
        template_id = self.env.ref(f'ot_management.{string}').id
        template = self.env['mail.template'].browse(template_id)
        template.send_mail(self.id, force_send=True)

    @api.depends('state')
    def _compute_hide_edit_button(self):
        for record in self:
            if record.state != 'draft':
                record.hide_edit_button = '<style>.o_form_button_edit {display: none !important;}</style>'
            else:
                record.hide_edit_button = False

    @api.model
    def create(self, vals):
        if not vals.get('res_ot_line_ids'):
            raise UserError('Chưa nhập OT line')
        else:
            res = super(EmployeeOt, self).create(vals)
        return res

    def unlink(self):
        for rec in self:
            user = self.env.user
            if user != rec.user_id:
                raise UserError('Bạn không có quyền xóa bản ghi này')
            if rec.state == 'dl_approved':
                raise UserError('Bản ghi đã được duyệt, không được phép chỉnh sửa')
        return super(EmployeeOt, self).unlink()

    @api.depends('state')
    def _compute_hide_delete_button(self):
        for record in self:
            if record.state == 'dl_approved':
                record.hide_delete_button = '<style>.o_dropdown {display: none !important;}</style>'
            else:
                record.hide_delete_button = False

    @api.multi
    def pm_approve_button(self):
        for rec in self:
            rec.send_email('pm_approved_email_template')
            rec.write({'state': 'pm_approved'})

    @api.multi
    def dl_approve_button(self):
        for rec in self:
            rec.write({'state': 'dl_approved'})
            rec.send_email('dl_approved_email_template')

    @api.multi
    def pm_refuse_button(self):
        for rec in self:
            rec.send_email('pm_rejected_ot_email_template')
            rec.write({'state': 'dl_refused'})

    @api.multi
    def dl_refuse_button(self):
        for rec in self:
            rec.write({'state': 'dl_refused'})
            rec.send_email('dl_rejected_ot_email_template')

    @api.multi
    def button_done(self):
        for rec in self:
            rec.send_email('create_ot_line_email_template')
            rec.write({'state': 'to_approve'})

    @api.multi
    def set_to_draft_button(self):
        for rec in self:
            user = self.env.user
            if user == rec.user_id:
                rec.write({'state': 'draft'})
            else:
                raise ValidationError("Bạn không có quyền set bản ghi này về draft")

    @api.depends('res_ot_line_ids.ot_hours')
    def _compute_line_total_ot(self):
        for rec in self:
            if rec.res_ot_line_ids and rec.res_ot_line_ids.filtered(lambda x: x.ot_hours):
                total_ot = 0
                for x in rec.res_ot_line_ids.filtered(lambda x: x.ot_hours):
                    total_ot += x.ot_hours
                rec.update({'line_total_ot': total_ot})

    @api.depends('res_ot_line_ids.ot_from')
    def _compute_ot_month(self):
        for rec in self:
            if rec.res_ot_line_ids and rec.res_ot_line_ids.filtered(lambda x: x.ot_from):
                ot_line_1 = rec.res_ot_line_ids.filtered(lambda x: x.ot_from)
                rec.line_ot_month = ot_line_1[0].ot_from.strftime("%m/%Y")

    def get_some_text(self):
        if self.state == 'dl_approved':
            return 'Bản ghi OT đã được duyệt'
        elif self.state == 'to_approve' or 'dl_refused':
            return 'Bản ghi OT đã bị từ chối'


class EmployeeOtLine(models.Model):
    _name = 'res.ot.line'

    ot_from = fields.Datetime(string='From', required=True)
    ot_to = fields.Datetime(string='To', required=True)
    ot_category = fields.Selection([
        ('saturday', 'Thứ bảy'),
        ('sunday', 'Chủ nhật')
    ])
    wfh = fields.Boolean(string='WFH')
    ot_hours = fields.Integer(compute='_compute_ot_hours', compute_sudo=True)
    job_taken = fields.Char(string='Job Taken')
    late_approved = fields.Boolean(string='Late Approved')
    attendance_notes = fields.Char(string='Attendance Notes')
    warning = fields.Char(string='Warning')
    employee_ot_id = fields.Many2one('res.ot', string='Employee OT Id')
    hr_notes = fields.Char(string='HR Notes')
    state = fields.Selection(string='State', related='employee_ot_id.state')

    @api.depends('ot_from', 'ot_to')
    def _compute_ot_hours(self):
        for rec in self:
            if rec.ot_to and rec.ot_from:
                difference_in_second = (rec.ot_to - rec.ot_from).total_seconds()
                rec.ot_hours = difference_in_second / 3600.0
                if rec.ot_hours > 8:
                    rec.ot_hours = 8
                    rec.warning = 'Exceed OT plan'
                else:
                    rec.warning = ''
            # rec.update({'ot_hours': rec.ot_hours})

    @api.constrains('ot_from', 'ot_to')
    def check_ot_from(self):
        for rec in self:
            if rec.ot_from > rec.ot_to:
                raise ValidationError("To không được nhỏ hơn from")
            else:
                ot_create_date = rec.employee_ot_id.create_date
                difference_in_day = ((ot_create_date - rec.ot_from).total_seconds()) / 86400.0
                if difference_in_day > 2:
                    raise ValidationError(f'Bản ghi OT ngày {rec.ot_from.strftime("%d/%m/%Y")} của bạn đã quá thời hạn log')
