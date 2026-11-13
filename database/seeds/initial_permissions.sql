INSERT INTO consumer_questionnaire.roles (code, name, description) VALUES
    ('administrator', 'Administrator', 'Manage users, roles and all questionnaire data.'),
    ('data_editor', 'Data editor', 'View, create, update and import questionnaire data.'),
    ('analyst', 'Analyst', 'View, analyze and export questionnaire data.'),
    ('viewer', 'Viewer', 'View questionnaire data only.');

INSERT INTO consumer_questionnaire.permissions (code, name) VALUES
    ('data:view', 'View questionnaire data'),
    ('data:create', 'Create questionnaire data'),
    ('data:update', 'Update questionnaire data'),
    ('data:import', 'Import questionnaire data'),
    ('data:delete', 'Delete questionnaire data'),
    ('data:export', 'Export questionnaire data'),
    ('analytics:view', 'View statistics and analysis'),
    ('users:manage', 'Manage users and user role assignments'),
    ('roles:manage', 'Manage roles and role permission assignments'),
    ('audit:view', 'View audit logs');

INSERT INTO consumer_questionnaire.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM consumer_questionnaire.roles AS r
CROSS JOIN consumer_questionnaire.permissions AS p
WHERE r.code = 'administrator'
   OR (r.code = 'data_editor' AND p.code IN (
       'data:view', 'data:create', 'data:update', 'data:import'
   ))
   OR (r.code = 'analyst' AND p.code IN (
       'data:view', 'data:export', 'analytics:view'
   ))
   OR (r.code = 'viewer' AND p.code = 'data:view');
