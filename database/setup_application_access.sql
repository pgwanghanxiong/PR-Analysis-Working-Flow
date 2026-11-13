\set ON_ERROR_STOP on
\encoding UTF8

SELECT current_database() = 'Consumer Questionnaire' AS correct_database \gset
\if :correct_database
\else
    \echo 'ERROR: connect to Consumer Questionnaire before configuring access.'
    \quit 1
\endif

BEGIN;

CREATE ROLE consumer_questionnaire_app
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

REVOKE ALL ON DATABASE "Consumer Questionnaire" FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

GRANT CONNECT ON DATABASE "Consumer Questionnaire" TO consumer_questionnaire_app;
GRANT USAGE ON SCHEMA consumer_questionnaire TO consumer_questionnaire_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    consumer_questionnaire.users,
    consumer_questionnaire.roles,
    consumer_questionnaire.user_roles,
    consumer_questionnaire.role_permissions,
    consumer_questionnaire.questionnaire_data
TO consumer_questionnaire_app;

GRANT SELECT ON consumer_questionnaire.permissions TO consumer_questionnaire_app;
GRANT SELECT, INSERT ON consumer_questionnaire.audit_logs TO consumer_questionnaire_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA consumer_questionnaire
    TO consumer_questionnaire_app;
GRANT EXECUTE ON FUNCTION consumer_questionnaire.set_updated_at()
    TO consumer_questionnaire_app;

COMMIT;
