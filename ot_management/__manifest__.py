{
    'name': "OT management",
    'version': '1.0',
    'depends': ['base', 'mail', 'hr', 'project'],
    'author': "VMS",
    'company': "VTI",
    'category': 'Category',
    'description': "Test project",
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/mail_template.xml',
        'views/ot_view.xml',
        'views/ot_line_view.xml'
    ],
    'image': [],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}