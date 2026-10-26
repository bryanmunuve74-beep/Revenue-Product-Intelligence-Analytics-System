PROJECT 2 DATA GENERATOR — QUICK START (WINDOWS POWERSHELL)

1. Download project2_generate_dataset.py.
2. Open PowerShell in the folder where you saved the file.
3. Install dependencies:
   py -m pip install pandas numpy Faker
4. Run the generator:
   py project2_generate_dataset.py --sessions 10000 --seed 42 --out-dir project2_data

The script creates project2_data with:
- analytics_sessions.csv
- analytics_events.csv
- orders.csv
- 00_create_source_tables.sql
- dataset_summary.txt

Important:
- Use at least 1000 sessions. The recommended value is 10000.
- The script does not connect to PostgreSQL and does not send data to GA4 or M-Pesa.
- Create/use a separate Project 2 database or schema; don't import these sample records into your Project 1 production/payment tables.
- Import order: analytics_sessions.csv, orders.csv, analytics_events.csv.

If it still fails, copy the complete PowerShell error message and send it back; the exact last lines usually identify the cause.
