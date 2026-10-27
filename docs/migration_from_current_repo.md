# Applying this solution to the current repository

This bundle is a clean, consistent replacement layout for the current repository. The existing repo had two different staging SQL files, a Compose file that reused Project 1's database name/port/container naming, and generated CSVs containing phone-shaped values. Do not mix the old and new SQL implementations.

1. Make a Git commit or branch before replacing files.
2. Copy the files from this bundle into the repository root, keeping the directory structure in the README.
3. Remove the old `project2_data/` directory after confirming it contains only the old Project 2 CSVs, SQL, and dashboard. Its staging SQL refers to columns that are not in the source schema and should no longer be used.
4. Remove the old Node-only `package.json` and `package-lock.json` because this project is Python-based. `node_modules/` should not be committed.
5. Restore `.env` from `.env.example` locally, but never commit `.env`.
6. Generate a fresh synthetic dataset, then run the database steps from the root README. Do not import old CSVs into the new schema.
7. Commit the code, SQL, tests, and documentation. The generated `data/*.csv` files and `analysis/output/` are ignored by Git.

The new Compose setup is configured for port 5433 and database `project2_analytics` to avoid intentionally sharing Project 1's typical port 5432/database. If port 5433 is already occupied, change `HOST_DB_PORT` and the port in `DATABASE_URL` together in `.env`.
