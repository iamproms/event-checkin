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
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_jobs') THEN
    CREATE ROLE eventcheckin_jobs NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_jobs_app') THEN
    CREATE ROLE eventcheckin_jobs_app LOGIN PASSWORD 'local_jobs_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_dispatcher') THEN
    CREATE ROLE eventcheckin_dispatcher NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_dispatcher_app') THEN
    CREATE ROLE eventcheckin_dispatcher_app LOGIN PASSWORD 'local_dispatcher_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_job_operator') THEN
    CREATE ROLE eventcheckin_job_operator NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_job_operator_app') THEN
    CREATE ROLE eventcheckin_job_operator_app LOGIN PASSWORD 'local_operator_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_platform') THEN
    CREATE ROLE eventcheckin_platform NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_platform_app') THEN
    CREATE ROLE eventcheckin_platform_app LOGIN PASSWORD 'local_platform_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_bootstrap') THEN
    CREATE ROLE eventcheckin_bootstrap NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_bootstrap_app') THEN
    CREATE ROLE eventcheckin_bootstrap_app LOGIN PASSWORD 'local_bootstrap_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_domain_worker') THEN
    CREATE ROLE eventcheckin_domain_worker NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_domain_worker_app') THEN
    CREATE ROLE eventcheckin_domain_worker_app LOGIN PASSWORD 'local_domain_worker_only' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_domain_scheduler') THEN
    CREATE ROLE eventcheckin_domain_scheduler NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_domain_scheduler_app') THEN
    CREATE ROLE eventcheckin_domain_scheduler_app LOGIN PASSWORD 'local_domain_scheduler_only' NOBYPASSRLS;
  END IF;
END $$;
GRANT eventcheckin_runtime TO eventcheckin_app;
GRANT eventcheckin_identity TO eventcheckin_identity_app;
GRANT eventcheckin_jobs TO eventcheckin_jobs_app;
GRANT eventcheckin_dispatcher TO eventcheckin_dispatcher_app;
GRANT eventcheckin_job_operator TO eventcheckin_job_operator_app;
GRANT eventcheckin_platform TO eventcheckin_platform_app;
GRANT eventcheckin_bootstrap TO eventcheckin_bootstrap_app;
GRANT eventcheckin_domain_worker TO eventcheckin_domain_worker_app;
GRANT eventcheckin_domain_scheduler TO eventcheckin_domain_scheduler_app;
GRANT eventcheckin_domain_resolver TO eventcheckin;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_identity_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_jobs_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_dispatcher_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_job_operator_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_platform_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_bootstrap_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_domain_worker_app;
GRANT CONNECT ON DATABASE eventcheckin TO eventcheckin_domain_scheduler_app;
