CREATE SCHEMA consumer_questionnaire;

CREATE TABLE consumer_questionnaire.users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL UNIQUE CHECK (btrim(username) <> ''),
    password_hash text NOT NULL CHECK (btrim(password_hash) <> ''),
    display_name text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE consumer_questionnaire.roles (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (btrim(code) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    description text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE consumer_questionnaire.permissions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (btrim(code) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    description text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE consumer_questionnaire.user_roles (
    user_id bigint NOT NULL REFERENCES consumer_questionnaire.users(id) ON DELETE CASCADE,
    role_id bigint NOT NULL REFERENCES consumer_questionnaire.roles(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX user_roles_role_id_idx ON consumer_questionnaire.user_roles (role_id);

CREATE TABLE consumer_questionnaire.role_permissions (
    role_id bigint NOT NULL REFERENCES consumer_questionnaire.roles(id) ON DELETE CASCADE,
    permission_id bigint NOT NULL REFERENCES consumer_questionnaire.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX role_permissions_permission_id_idx
    ON consumer_questionnaire.role_permissions (permission_id);

CREATE TABLE consumer_questionnaire.questionnaire_data (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "1_Study" text NOT NULL CHECK (btrim("1_Study") <> ''),
    "2_Respondent Serial Number" text NOT NULL CHECK (btrim("2_Respondent Serial Number") <> ''),
    "3_Day" integer NOT NULL CHECK ("3_Day" >= 0),
    "4_Leg" text NOT NULL CHECK (btrim("4_Leg") <> ''),
    "5_Dqs" text NOT NULL CHECK (btrim("5_Dqs") <> ''),
    "6_Value" numeric NOT NULL CHECK (
        "6_Value" NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
    ),
    created_by bigint REFERENCES consumer_questionnaire.users(id) ON DELETE SET NULL,
    updated_by bigint REFERENCES consumer_questionnaire.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX questionnaire_data_study_respondent_day_idx
    ON consumer_questionnaire.questionnaire_data
    ("1_Study", "2_Respondent Serial Number", "3_Day");

CREATE INDEX questionnaire_data_created_by_idx
    ON consumer_questionnaire.questionnaire_data (created_by);

CREATE INDEX questionnaire_data_updated_by_idx
    ON consumer_questionnaire.questionnaire_data (updated_by);

CREATE TABLE consumer_questionnaire.audit_logs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id bigint REFERENCES consumer_questionnaire.users(id) ON DELETE SET NULL,
    action text NOT NULL CHECK (btrim(action) <> ''),
    entity_type text NOT NULL CHECK (btrim(entity_type) <> ''),
    entity_id text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX audit_logs_actor_time_idx
    ON consumer_questionnaire.audit_logs (actor_user_id, created_at);

CREATE INDEX audit_logs_entity_idx
    ON consumer_questionnaire.audit_logs (entity_type, entity_id);

CREATE FUNCTION consumer_questionnaire.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON consumer_questionnaire.users
    FOR EACH ROW EXECUTE FUNCTION consumer_questionnaire.set_updated_at();

CREATE TRIGGER roles_set_updated_at
    BEFORE UPDATE ON consumer_questionnaire.roles
    FOR EACH ROW EXECUTE FUNCTION consumer_questionnaire.set_updated_at();

CREATE TRIGGER questionnaire_data_set_updated_at
    BEFORE UPDATE ON consumer_questionnaire.questionnaire_data
    FOR EACH ROW EXECUTE FUNCTION consumer_questionnaire.set_updated_at();

REVOKE ALL ON SCHEMA consumer_questionnaire FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA consumer_questionnaire FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA consumer_questionnaire FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA consumer_questionnaire FROM PUBLIC;

COMMENT ON COLUMN consumer_questionnaire.questionnaire_data."1_Study"
    IS 'Study identifier or name.';
COMMENT ON COLUMN consumer_questionnaire.questionnaire_data."2_Respondent Serial Number"
    IS 'Respondent identifier stored as text to preserve leading zeros.';
COMMENT ON COLUMN consumer_questionnaire.questionnaire_data."3_Day"
    IS 'Non-negative day number; zero can represent a baseline day.';
COMMENT ON COLUMN consumer_questionnaire.questionnaire_data."4_Leg"
    IS 'Product name.';
COMMENT ON COLUMN consumer_questionnaire.questionnaire_data."5_Dqs"
    IS 'Questionnaire question.';
COMMENT ON COLUMN consumer_questionnaire.questionnaire_data."6_Value"
    IS 'Finite numeric answer without a fixed precision or scale.';
