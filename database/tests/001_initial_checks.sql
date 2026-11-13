\set ON_ERROR_STOP on
\encoding UTF8

SELECT current_database() = 'Consumer Questionnaire' AS correct_database \gset
\if :correct_database
\else
    \echo 'ERROR: connect to Consumer Questionnaire before running checks.'
    \quit 1
\endif

BEGIN;

DO $$
DECLARE
    test_user_id bigint;
    test_data_id bigint;
    actual_columns text[];
    actual_types text[];
BEGIN
    SELECT array_agg(column_name::text ORDER BY ordinal_position),
           array_agg(data_type::text ORDER BY ordinal_position)
    INTO actual_columns, actual_types
    FROM information_schema.columns
    WHERE table_schema = 'consumer_questionnaire'
      AND table_name = 'questionnaire_data';

    IF actual_columns IS DISTINCT FROM ARRAY[
        'id', '1_Study', '2_Respondent Serial Number', '3_Day',
        '4_Leg', '5_Dqs', '6_Value', 'created_by', 'updated_by',
        'created_at', 'updated_at'
    ]::text[] THEN
        RAISE EXCEPTION 'Unexpected questionnaire_data columns: %', actual_columns;
    END IF;

    IF actual_types IS DISTINCT FROM ARRAY[
        'bigint', 'text', 'text', 'integer', 'text', 'text', 'numeric',
        'bigint', 'bigint', 'timestamp with time zone', 'timestamp with time zone'
    ]::text[] THEN
        RAISE EXCEPTION 'Unexpected questionnaire_data types: %', actual_types;
    END IF;

    IF (SELECT count(*) FROM consumer_questionnaire.roles) <> 4
       OR (SELECT count(*) FROM consumer_questionnaire.permissions) <> 10
       OR (SELECT count(*) FROM consumer_questionnaire.role_permissions) <> 18 THEN
        RAISE EXCEPTION 'Unexpected initial role or permission counts';
    END IF;

    IF EXISTS (
        WITH expected AS (
            SELECT r.id AS role_id, p.id AS permission_id
            FROM consumer_questionnaire.roles AS r
            CROSS JOIN consumer_questionnaire.permissions AS p
            WHERE r.code = 'administrator'
               OR (r.code = 'data_editor' AND p.code IN (
                   'data:view', 'data:create', 'data:update', 'data:import'
               ))
               OR (r.code = 'analyst' AND p.code IN (
                   'data:view', 'data:export', 'analytics:view'
               ))
               OR (r.code = 'viewer' AND p.code = 'data:view')
        )
        (SELECT role_id, permission_id FROM expected
         EXCEPT SELECT role_id, permission_id FROM consumer_questionnaire.role_permissions)
        UNION ALL
        (SELECT role_id, permission_id FROM consumer_questionnaire.role_permissions
         EXCEPT SELECT role_id, permission_id FROM expected)
    ) THEN
        RAISE EXCEPTION 'Unexpected initial role permission assignments';
    END IF;

    INSERT INTO consumer_questionnaire.users (username, password_hash)
    VALUES ('cq_schema_test_' || txid_current()::text, 'TEST_ONLY_NOT_A_REAL_HASH')
    RETURNING id INTO test_user_id;

    INSERT INTO consumer_questionnaire.questionnaire_data (
        "1_Study", "2_Respondent Serial Number", "3_Day", "4_Leg",
        "5_Dqs", "6_Value", created_by, updated_by
    ) VALUES (
        'DEMO_STUDY', '000001', 0, 'Demo product',
        'Demo question', 1.23456789, test_user_id, test_user_id
    ) RETURNING id INTO test_data_id;

    IF NOT EXISTS (
        SELECT 1 FROM consumer_questionnaire.questionnaire_data
        WHERE id = test_data_id
          AND "2_Respondent Serial Number" = '000001'
          AND "6_Value" = 1.23456789
    ) THEN
        RAISE EXCEPTION 'Leading zeros or numeric precision were not preserved';
    END IF;

    UPDATE consumer_questionnaire.questionnaire_data
    SET updated_at = '2000-01-01 00:00:00+00'
    WHERE id = test_data_id;

    IF NOT EXISTS (
        SELECT 1 FROM consumer_questionnaire.questionnaire_data
        WHERE id = test_data_id AND updated_at = CURRENT_TIMESTAMP
    ) THEN
        RAISE EXCEPTION 'Updated timestamp trigger did not run';
    END IF;

    BEGIN
        UPDATE consumer_questionnaire.questionnaire_data
        SET "3_Day" = -1 WHERE id = test_data_id;
        RAISE EXCEPTION 'Negative day was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    BEGIN
        UPDATE consumer_questionnaire.questionnaire_data
        SET "6_Value" = 'NaN'::numeric WHERE id = test_data_id;
        RAISE EXCEPTION 'NaN was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    BEGIN
        UPDATE consumer_questionnaire.questionnaire_data
        SET "6_Value" = 'Infinity'::numeric WHERE id = test_data_id;
        RAISE EXCEPTION 'Infinity was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    BEGIN
        UPDATE consumer_questionnaire.questionnaire_data
        SET "6_Value" = '-Infinity'::numeric WHERE id = test_data_id;
        RAISE EXCEPTION 'Negative infinity was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    BEGIN
        UPDATE consumer_questionnaire.questionnaire_data
        SET "5_Dqs" = ' ' WHERE id = test_data_id;
        RAISE EXCEPTION 'Blank question was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    BEGIN
        UPDATE consumer_questionnaire.questionnaire_data
        SET "6_Value" = NULL WHERE id = test_data_id;
        RAISE EXCEPTION 'NULL value was accepted';
    EXCEPTION WHEN not_null_violation THEN
        NULL;
    END;

    DELETE FROM consumer_questionnaire.users WHERE id = test_user_id;
    IF NOT EXISTS (
        SELECT 1 FROM consumer_questionnaire.questionnaire_data
        WHERE id = test_data_id AND created_by IS NULL AND updated_by IS NULL
    ) THEN
        RAISE EXCEPTION 'Deleting a user did not preserve questionnaire data';
    END IF;

    RAISE NOTICE 'Initial schema, permission and data checks passed; test rows will be rolled back.';
END;
$$;

ROLLBACK;
