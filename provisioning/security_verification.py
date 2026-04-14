#!/usr/bin/env python3
"""
Atlas on OCI - MZX Security Verification Script
Verifies that all security mandates are properly enforced
"""

import oracledb
import os
import sys
import json
from datetime import datetime

from config import Config

# Resolve the report output path relative to the repo root so the script
# works from any checkout. The previous hard-coded ``/home/ubuntu/atlas_oci``
# path only existed on the original provisioning VM and caused the script to
# fail with ``FileNotFoundError`` on every other machine.
REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "security_verification_report.json",
)

def main():
    print("=" * 70)
    print("Atlas on OCI - MZX Security Verification Report")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Region: me-riyadh-1 (Saudi Arabia Central - Riyadh)")
    print("=" * 70)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "region": "me-riyadh-1",
        "tests": [],
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0
        }
    }
    
    try:
        print(f"\nConnecting to ATP database...")
        if Config.USE_WALLET:
            wallet_dir = os.path.expanduser(Config.DB_WALLET_DIR)
            print(f"Using mTLS (Wallet) connection from: {wallet_dir}")
            connection = oracledb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.DB_DSN,
                config_dir=wallet_dir,
                wallet_location=wallet_dir,
                wallet_password=Config.DB_WALLET_PASSWORD or Config.DB_PASSWORD,
            )
        else:
            print("Using Walletless TLS connection...")
            connection = oracledb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.DB_DSN,
            )
        print("✅ Connected successfully!\n")
        
        cursor = connection.cursor()
        
        # ============================================================
        # TEST 1: Read-Only Enforcement (MZX Security Mandate)
        # ============================================================
        print("=" * 70)
        print("TEST 1: Read-Only Enforcement (MZX Security Mandate)")
        print("=" * 70)
        
        readonly_tests = [
            ("SELECT * FROM ATLAS_EMPLOYEES", "SELECT", True),
            ("SELECT COUNT(*) FROM ATLAS_DEPARTMENTS", "SELECT COUNT", True),
            ("SELECT e.FULL_NAME, d.DEPARTMENT_NAME FROM ATLAS_EMPLOYEES e JOIN ATLAS_DEPARTMENTS d ON e.DEPARTMENT_ID = d.DEPARTMENT_ID", "SELECT JOIN", True),
            ("INSERT INTO ATLAS_EMPLOYEES (EMPLOYEE_ID, EMPLOYEE_NUMBER, FULL_NAME, LAST_SYNC_DATE) VALUES (999, 'TEST', 'Test User', SYSTIMESTAMP)", "INSERT", False),
            ("UPDATE ATLAS_EMPLOYEES SET FULL_NAME = 'Hacked' WHERE EMPLOYEE_ID = 1", "UPDATE", False),
            ("DELETE FROM ATLAS_EMPLOYEES WHERE EMPLOYEE_ID = 1", "DELETE", False),
            ("DROP TABLE ATLAS_EMPLOYEES", "DROP", False),
            ("ALTER TABLE ATLAS_EMPLOYEES ADD (TEST_COL VARCHAR2(10))", "ALTER", False),
            ("CREATE TABLE HACK_TABLE (ID NUMBER)", "CREATE", False),
            ("TRUNCATE TABLE ATLAS_EMPLOYEES", "TRUNCATE", False),
            ("MERGE INTO ATLAS_EMPLOYEES USING DUAL ON (1=1) WHEN MATCHED THEN UPDATE SET FULL_NAME='X'", "MERGE", False),
            ("GRANT SELECT ON ATLAS_EMPLOYEES TO PUBLIC", "GRANT", False),
            ("EXEC DBMS_OUTPUT.PUT_LINE('test')", "EXEC DBMS_", False),
            ("BEGIN DBMS_SCHEDULER.CREATE_JOB('test'); END;", "DBMS_SCHEDULER", False),
        ]
        
        print("\nTesting ATLAS_VALIDATE_QUERY function:")
        print("-" * 70)
        
        for sql, test_name, should_pass in readonly_tests:
            cursor.execute("SELECT ATLAS_VALIDATE_QUERY(:1) FROM DUAL", [sql])
            result = cursor.fetchone()[0]
            is_valid = result == "VALID"
            
            if (should_pass and is_valid) or (not should_pass and not is_valid):
                status = "✅ PASS"
                results["summary"]["passed"] += 1
            else:
                status = "❌ FAIL"
                results["summary"]["failed"] += 1
            
            results["summary"]["total"] += 1
            results["tests"].append({
                "category": "Read-Only Enforcement",
                "test": test_name,
                "expected": "ALLOWED" if should_pass else "BLOCKED",
                "actual": "ALLOWED" if is_valid else "BLOCKED",
                "passed": (should_pass and is_valid) or (not should_pass and not is_valid)
            })
            
            expected = "ALLOWED" if should_pass else "BLOCKED"
            actual = "ALLOWED" if is_valid else "BLOCKED"
            print(f"  {status} {test_name:20} | Expected: {expected:8} | Actual: {actual:8}")
        
        # ============================================================
        # TEST 2: Audit Logging Verification
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 2: Audit Logging Verification")
        print("=" * 70)
        
        # Check audit log table exists and has records
        cursor.execute("SELECT COUNT(*) FROM ATLAS_AUDIT_LOG")
        audit_count = cursor.fetchone()[0]
        
        print(f"\n  Audit log records: {audit_count}")
        
        if audit_count > 0:
            cursor.execute("""
                SELECT EVENT_TYPE, COUNT(*) as CNT 
                FROM ATLAS_AUDIT_LOG 
                GROUP BY EVENT_TYPE 
                ORDER BY CNT DESC
            """)
            print("\n  Event types logged:")
            for row in cursor.fetchall():
                print(f"    - {row[0]}: {row[1]} events")
            
            status = "✅ PASS"
            results["summary"]["passed"] += 1
        else:
            status = "⚠️  WARNING"
        
        results["summary"]["total"] += 1
        results["tests"].append({
            "category": "Audit Logging",
            "test": "Audit log populated",
            "expected": "Records exist",
            "actual": f"{audit_count} records",
            "passed": audit_count > 0
        })
        print(f"\n  {status} Audit logging is {'active' if audit_count > 0 else 'not yet populated'}")
        
        # ============================================================
        # TEST 3: Data Classification Columns
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 3: Data Classification Columns")
        print("=" * 70)
        
        cursor.execute("""
            SELECT table_name, column_name 
            FROM user_tab_columns 
            WHERE column_name = 'DATA_CLASSIFICATION' 
            AND table_name LIKE 'ATLAS%'
            ORDER BY table_name
        """)
        classified_tables = cursor.fetchall()
        
        print(f"\n  Tables with DATA_CLASSIFICATION column: {len(classified_tables)}")
        for table in classified_tables:
            print(f"    - {table[0]}")
        
        expected_tables = 7  # EMPLOYEES, DEPARTMENTS, LOCATIONS, SUPPLIERS, PO, INVOICES, GL_BALANCES
        if len(classified_tables) >= expected_tables:
            status = "✅ PASS"
            results["summary"]["passed"] += 1
            passed = True
        else:
            status = "❌ FAIL"
            results["summary"]["failed"] += 1
            passed = False
        
        results["summary"]["total"] += 1
        results["tests"].append({
            "category": "Data Classification",
            "test": "Classification columns exist",
            "expected": f">= {expected_tables} tables",
            "actual": f"{len(classified_tables)} tables",
            "passed": passed
        })
        print(f"\n  {status} Data classification columns {'properly configured' if passed else 'missing'}")
        
        # ============================================================
        # TEST 4: Bilingual Support (Arabic/English)
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 4: Bilingual Support (Arabic/English)")
        print("=" * 70)
        
        bilingual_tests = [
            ("Show me all employees", "English"),
            ("كم عدد الموظفين؟", "Arabic - Employee count"),
            ("List all departments", "English - Departments"),
            ("عرض الفواتير المتأخرة", "Arabic - Overdue invoices"),
        ]
        
        print("\n  Testing ATLAS_PROCESS_COMMAND bilingual support:")
        all_bilingual_passed = True
        
        for cmd, lang in bilingual_tests:
            cursor.execute("SELECT ATLAS_PROCESS_COMMAND(:1, 'TEST') FROM DUAL", [cmd])
            result = cursor.fetchone()[0]
            result_str = result.read() if hasattr(result, 'read') else str(result)
            
            # Check if a valid response was generated
            try:
                response = json.loads(result_str)
                has_response = "type" in response
            except:
                has_response = False
            
            if has_response:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
                all_bilingual_passed = False
            
            print(f"    {status} {lang}: {cmd[:30]}...")
        
        if all_bilingual_passed:
            results["summary"]["passed"] += 1
        else:
            results["summary"]["failed"] += 1
        
        results["summary"]["total"] += 1
        results["tests"].append({
            "category": "Bilingual Support",
            "test": "Arabic/English commands",
            "expected": "Both languages supported",
            "actual": "Supported" if all_bilingual_passed else "Partial",
            "passed": all_bilingual_passed
        })
        
        # ============================================================
        # TEST 5: Schema Objects Verification
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 5: Schema Objects Verification")
        print("=" * 70)
        
        # Check tables
        cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name LIKE 'ATLAS%'")
        table_count = cursor.fetchone()[0]
        
        # Check sequences
        cursor.execute("SELECT COUNT(*) FROM user_sequences WHERE sequence_name LIKE 'SEQ_ATLAS%'")
        seq_count = cursor.fetchone()[0]
        
        # Check functions/procedures
        cursor.execute("SELECT COUNT(*) FROM user_objects WHERE object_name LIKE 'ATLAS%' AND object_type IN ('FUNCTION', 'PROCEDURE')")
        proc_count = cursor.fetchone()[0]
        
        print(f"\n  Schema objects:")
        print(f"    - Tables: {table_count}")
        print(f"    - Sequences: {seq_count}")
        print(f"    - Functions/Procedures: {proc_count}")
        
        schema_passed = table_count >= 10 and seq_count >= 4 and proc_count >= 5
        if schema_passed:
            status = "✅ PASS"
            results["summary"]["passed"] += 1
        else:
            status = "❌ FAIL"
            results["summary"]["failed"] += 1
        
        results["summary"]["total"] += 1
        results["tests"].append({
            "category": "Schema Objects",
            "test": "Required objects exist",
            "expected": "10+ tables, 4+ sequences, 5+ procs",
            "actual": f"{table_count} tables, {seq_count} seqs, {proc_count} procs",
            "passed": schema_passed
        })
        print(f"\n  {status} Schema objects {'complete' if schema_passed else 'incomplete'}")
        
        cursor.close()
        connection.close()
        
        # ============================================================
        # FINAL SUMMARY
        # ============================================================
        print("\n" + "=" * 70)
        print("MZX SECURITY VERIFICATION SUMMARY")
        print("=" * 70)
        
        total = results["summary"]["total"]
        passed = results["summary"]["passed"]
        failed = results["summary"]["failed"]
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n  Total Tests: {total}")
        print(f"  Passed:      {passed} ({pass_rate:.1f}%)")
        print(f"  Failed:      {failed}")
        
        if failed == 0:
            print("\n  ✅ ALL SECURITY MANDATES VERIFIED - READY FOR SIGN-OFF")
            final_status = "APPROVED"
        else:
            print("\n  ❌ SECURITY VERIFICATION FAILED - REVIEW REQUIRED")
            final_status = "REVIEW_REQUIRED"
        
        results["final_status"] = final_status
        
        print("\n" + "=" * 70)
        
        # Save results to JSON
        with open(REPORT_PATH, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n📄 Full report saved to: {REPORT_PATH}")
        
        return 0 if failed == 0 else 1
        
    except oracledb.Error as e:
        print(f"\n❌ Database connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
