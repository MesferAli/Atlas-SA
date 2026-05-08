"""Deploy Atlas's Oracle E-Business Suite integration package into ATP.

Mirrors deploy_fusion_integration.py — connects to the configured ATP
instance, splits atlas_ebs_sync.sql on the SQL*Plus '/' separator, and
executes each chunk in order. The package itself is installed even if
ATLAS_SOURCE_SYSTEM is still pointing at FUSION; the runtime guard in
ATLAS_EBS_SYNC_PKG.SYNC_ALL_EBS_DATA prevents the scheduled job from
double-syncing in that case.

Pre-requisites:
  1. The DB link named in EBS_DB_LINK (default EBS_PROD) must already
     exist in ATP and resolve to a reachable EBS APPS schema. Create it
     manually with CREATE DATABASE LINK before running this deploy.
  2. ATLAS_CONFIG_PKG must be deployed first (it provides the
     EBS_DB_LINK / EBS_APPS_SCHEMA getters this package consumes).
"""

import os
import sys

import oracledb

from config import Config


def _connect():
    wallet_dir = os.path.expanduser(Config.DB_WALLET_DIR)
    if Config.USE_WALLET:
        print(f"Configuring wallet from: {wallet_dir}")
        return oracledb.connect(
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            dsn=Config.DB_DSN,
            config_dir=wallet_dir,
            wallet_location=wallet_dir,
            wallet_password=Config.DB_WALLET_PASSWORD,
        )
    return oracledb.connect(
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        dsn=Config.DB_DSN,
    )


def main() -> int:
    print("=" * 60)
    print("Atlas on OCI - EBS Integration Deployment")
    print("=" * 60)
    print(f"Source system     : {Config.ATLAS_SOURCE_SYSTEM}")
    print(f"Integration mode  : {Config.EBS_INTEGRATION_MODE}")
    print(f"DB link target    : {Config.EBS_DB_LINK}")
    print(f"APPS schema       : {Config.EBS_APPS_SCHEMA}")
    print(f"Business group ID : {Config.EBS_BUSINESS_GROUP_ID}")
    print(f"Ledger ID         : {Config.EBS_LEDGER_ID}")
    print(f"Org (OU) ID       : {Config.EBS_ORG_ID}")

    try:
        print("\nConnecting to ATP database...")
        connection = _connect()
        print("Connected successfully.")

        cursor = connection.cursor()

        sql_path = os.path.join(os.path.dirname(__file__), "atlas_ebs_sync.sql")
        with open(sql_path, "r") as f:
            ebs_sql = f.read()

        # SQL*Plus convention: '/' on its own terminates a PL/SQL block. We
        # split on '/' and feed each non-empty chunk to oracledb.execute.
        sql_statements = [stmt.strip() for stmt in ebs_sql.split("/") if stmt.strip()]

        success_count = 0
        error_count = 0

        for i, stmt in enumerate(sql_statements, 1):
            try:
                cursor.execute(stmt)
                connection.commit()
                print(f"  [{i:02d}] Executed statement")
                success_count += 1
            except oracledb.DatabaseError as e:
                error = e.args[0]
                # ORA-00955 "name already in use" is fine on re-runs; the
                # CREATE OR REPLACE PACKAGE statements are idempotent on
                # their own, but the scheduler-job DECLARE block guards
                # itself with USER_SCHEDULER_JOBS so the only legitimate
                # benign error here is the link/grant being re-issued.
                if hasattr(error, "code") and error.code in (955, 2262, 942):
                    print(f"  [{i:02d}] Skipped (ORA-{error.code}, idempotent)")
                    success_count += 1
                else:
                    print(f"  [{i:02d}] Error: {error}")
                    error_count += 1

        cursor.close()
        connection.close()

        print("\n" + "=" * 60)
        print("EBS Integration Deployment Complete")
        print(f"  Success: {success_count}")
        print(f"  Errors : {error_count}")
        print("=" * 60)

        if Config.ATLAS_SOURCE_SYSTEM.upper() != "EBS":
            print(
                "\nNote: ATLAS_SOURCE_SYSTEM is still '"
                + Config.ATLAS_SOURCE_SYSTEM
                + "'. The scheduled EBS job is created but disabled; flip "
                "ATLAS_SOURCE_SYSTEM to 'EBS' (via ATLAS_CONFIG_PKG.SET_CONFIG_VALUE) "
                "and DBMS_SCHEDULER.ENABLE('ATLAS_DAILY_EBS_SYNC_JOB') to start syncing."
            )

        return 0 if error_count == 0 else 1

    except oracledb.Error as e:
        print(f"\nDatabase connection error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
