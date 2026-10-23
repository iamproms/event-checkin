-- Local development only. These fixed passwords are never production credentials.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_runtime') THEN
    CREATE ROLE eventcheckin_runtime NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_domain_resolver') THEN
    CREATE ROLE eventcheckin_domain_resolver NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_app') THEN
    CREATE ROLE eventcheckin_app LOGIN PASSWORD 'local_app_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_identity') THEN
    CREATE ROLE eventcheckin_identity NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_identity_app') THEN
    CREATE ROLE eventcheckin_identity_app LOGIN PASSWORD 'local_identity_only' NOBYPASSRLS;
  END IF;
END $$;
GRANT eventcheckin_runtime TO eventcheckin_app;
GRANT eventcheckin_identity TO eventcheckin_identity_app;
GRANT eventcheckin_domain_resolver TO eventcheckin;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_identity_app;
