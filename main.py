import hashlib
import logging
import os
import re
import sys
import time
from logging.handlers import RotatingFileHandler

import pyodbc
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Directory where your stored procedure .sql files are located
SP_SCRIPTS_DIR = "sql/stored_procedures"

# Table to store deployment metadata
DEPLOYMENT_METADATA_TABLE = "CUSTOM_StoredProcedureDeploymentMetadata"

# Setup logging
LOG_FILE = "logs/deployment.log"
# Ensure the log folder exists
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def get_db_connection():
    """Establishes and returns a database connection."""
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT")

    # Add this print statement for debugging
    logging.info(
        f"Attempting to connect with: Server={server}, User={username}, DB={database}, Port={port}"
    )

    if not all([server, database, username, password]):
        logging.error(
            "Database connection environment variables must be set: "
            "DB_SERVER, DB_DATABASE, DB_USERNAME, DB_PASSWORD, DB_PORT"
        )
        sys.exit(1)

    max_retries = 10
    retry_delay = 5  # seconds

    cnxn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password}"
    )

    for i in range(max_retries):
        try:
            cnxn = pyodbc.connect(cnxn_str)
            logging.info("Successfully connected to the database.")
            return cnxn
        except pyodbc.Error as ex:
            # Log warning for each failed attempt
            logging.warning(
                f"Attempt {i+1}/{max_retries}: Database connection error: {ex}"
            )
            time.sleep(retry_delay)

    # This line is only reached if the loop completes without returning
    logging.error("Failed to connect to the database after multiple retries.")
    sys.exit(1)


def calculate_file_hash(filepath):
    """Calculates the SHA256 hash of a file's content."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def ensure_metadata_table_exists(cursor, cnxn):
    """Checks if the deployment metadata table exists and creates it if not."""
    create_table_sql = f"""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{DEPLOYMENT_METADATA_TABLE}' and xtype='U')
    CREATE TABLE {DEPLOYMENT_METADATA_TABLE} (
        script_name VARCHAR(255) PRIMARY KEY,
        script_hash VARCHAR(64) NOT NULL,
        deployment_timestamp DATETIME DEFAULT GETDATE(),
        last_updated_timestamp DATETIME DEFAULT GETDATE()
    );
    """
    try:
        cursor.execute(create_table_sql)
        cnxn.commit()
        logging.info(f"Ensured '{DEPLOYMENT_METADATA_TABLE}' table exists.")
    except pyodbc.Error as ex:
        logging.error(f"Error ensuring metadata table exists: {ex}")
        sys.exit(1)


def get_deployed_hashes(cursor):
    """Fetches the names and hashes of currently deployed scripts from the database."""
    deployed_hashes = {}
    try:
        cursor.execute(
            f"SELECT script_name, script_hash FROM {DEPLOYMENT_METADATA_TABLE}"
        )
        for row in cursor.fetchall():
            deployed_hashes[row.script_name] = row.script_hash
    except pyodbc.Error as ex:
        logging.warning(f"Error fetching deployed hashes (may be first run): {ex}")
    return deployed_hashes


def update_deployment_metadata(cursor, cnxn, script_name, new_hash):
    """Inserts or updates the deployment metadata for a script."""
    try:
        merge_sql = f"""
        MERGE {DEPLOYMENT_METADATA_TABLE} AS target
        USING (SELECT ? AS script_name, ? AS script_hash) AS source
        ON target.script_name = source.script_name
        WHEN MATCHED THEN
            UPDATE SET script_hash = source.script_hash, last_updated_timestamp = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (script_name, script_hash, deployment_timestamp, last_updated_timestamp)
            VALUES (source.script_name, source.script_hash, GETDATE(), GETDATE());
        """
        cursor.execute(merge_sql, (script_name, new_hash))
        cnxn.commit()
        logging.info(f"Metadata updated for {script_name}.")
    except pyodbc.Error as ex:
        logging.error(f"Error updating metadata for {script_name}: {ex}")
        sys.exit(1)


def deploy_stored_procedures():
    """Main function to deploy stored procedures."""
    cnxn = get_db_connection()
    cursor = cnxn.cursor()

    ensure_metadata_table_exists(cursor, cnxn)
    deployed_hashes = get_deployed_hashes(cursor)

    deployed_count = 0
    skipped_count = 0
    error_count = 0

    if not os.path.exists(SP_SCRIPTS_DIR):
        logging.error(f"Stored procedures directory '{SP_SCRIPTS_DIR}' not found.")
        sys.exit(1)

    for filename in os.listdir(SP_SCRIPTS_DIR):
        if filename.endswith(".sql"):
            script_name = os.path.splitext(filename)[0]
            filepath = os.path.join(SP_SCRIPTS_DIR, filename)

            try:
                local_hash = calculate_file_hash(filepath)

                if (
                    script_name in deployed_hashes
                    and deployed_hashes[script_name] == local_hash
                ):
                    logging.info(f"Skipping '{filename}': No changes detected.")
                    skipped_count += 1
                    continue

                logging.info(f"Deploying '{filename}' (New or changed).")
                with open(filepath, "r", encoding="utf-8-sig") as file:
                    sql_script_content = file.read()

                # Split only on "GO" at line breaks
                statements = [
                    stmt.strip()
                    for stmt in re.split(r"(?im)^\s*GO\s*$", sql_script_content)
                    if stmt.strip()
                ]

                for i, stmt in enumerate(statements, 1):
                    try:
                        cursor.execute(stmt)
                        cnxn.commit()
                        logging.info(f"Executed statement {i} from {filename}.")
                    except Exception as e:
                        logging.error(f"Error in {filename}, statement {i}: {e}")
                        error_count += 1
                        cnxn.rollback()
                        break  # Stop executing further statements in this file

                if error_count == 0:
                    update_deployment_metadata(cursor, cnxn, script_name, local_hash)
                    logging.info(f"Successfully deployed: {filename}")
                    deployed_count += 1

            except pyodbc.Error as ex:
                logging.error(f"Error deploying {filename}: {ex}")
                error_count += 1
                cnxn.rollback()
            except Exception as e:
                logging.error(f"Unexpected error processing {filename}: {e}")
                error_count += 1
                cnxn.rollback()

    cnxn.close()
    logging.info("--- Deployment Summary ---")
    logging.info(f"Deployed: {deployed_count} stored procedures")
    logging.info(f"Skipped: {skipped_count} stored procedures (no changes)")
    logging.info(f"Errors: {error_count} stored procedures")

    if error_count > 0:
        logging.error("Deployment failed due to errors. Check logs.")
        sys.exit(1)
    else:
        logging.info("Deployment completed successfully.")
        sys.exit(0)


if __name__ == "__main__":
    deploy_stored_procedures()
