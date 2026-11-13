\set ON_ERROR_STOP on
\encoding UTF8

SELECT current_database() = 'Consumer Questionnaire' AS correct_database \gset
\if :correct_database
\else
    \echo 'ERROR: connect to Consumer Questionnaire before applying this migration.'
    \quit 1
\endif

BEGIN;
\ir ../schema/consumer_questionnaire.sql
\ir ../seeds/initial_permissions.sql
COMMIT;
