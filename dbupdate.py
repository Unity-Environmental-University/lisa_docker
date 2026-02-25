### script to initialize database with DAP data
### and keep it synchronized using command line

import os
import sys
import asyncio
import argparse
from datetime import datetime
from dap.api import DAPClient
from dap.integration.database import DatabaseConnection
from dap.replicator.sql import SQLReplicator, SQLDrop
from dap.log import configure_logging

import dotenv

dotenv.load_dotenv()

# -------- env vars ---------
## returns connection str for postgres db
def get_conn_str():
    db_user = os.environ.get("POSTGRES_USER")
    db_password = os.environ.get("POSTGRES_PW")
    db_host = os.environ.get("HOST")
    db_port = os.environ.get("PORT")
    db_name = os.environ.get("POSTGRES_DB")
        
    if all([db_user, db_password, db_host, db_port, db_name]):
        postgresql_connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    return postgresql_connection_string

# ---------- CLI ----------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canvas DAP Compliance Data Grabber")
    parser.add_argument(
        "operation",
        type=str,
        choices=["init", "sync"],
        help="Operation to perform: init(insert) tables from DAP into db or sync them"
    )

    parser.add_argument(
        "table_name_s",
        help="Table name(s): a string representing a single table, comma-separated list, or 'all'."
    )

    return parser

# ---------- table insertion ----------
## takes a list of table names (as a comma seperated str, not a list of strs) and pulls them from DAP
## into the database defined in the .env, either initializing or syncing the
## table as determined by the operation string. Note table_names being "all" will pull everything in
## the canvas namespace from the DAP, which is a lot of tables
async def init_or_sync_db_tables(table_names:str, operation:str) -> None:
    ## ensure log directory exists
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(BASE_DIR, "logs", "db_init_sync")
    os.makedirs(log_dir, exist_ok=True)

    ## build timestamped filename
    log_filename = os.path.join(
        log_dir,
        f"db_init_sync_{datetime.now().strftime('%Y%m%d')}.log"
    )

    # Configure logging to go into the new directory
    configure_logging(
        level="DEBUG",
        format="json",
        file=log_filename,
        namespace="canvas",
        table="accounts",
        client_id=os.environ.get("DAP_CLIENT_ID"),
    )

    ## connect to db
    db_connection_dap = DatabaseConnection(get_conn_str())
    

    ## use the DAPClient and SQLReplicator
    async with DAPClient() as session:
        sql_replicator = SQLReplicator(session, db_connection_dap)
        await sql_replicator.version_upgrade()
        dropper = SQLDrop(db_connection_dap)

        async def init_tables(namespace:str, table:str) -> None:
            await sql_replicator.initialize(namespace, table)

        async def sync_tables(namespace:str, table:str) -> None:
            await sql_replicator.synchronize(namespace, table)
            ## TODO temporarily removing drop and re-init fallback to see if fresh db solves sync issue
            # try:
            #     async with asyncio.timeout(10 * 60): # 10 min timeout per table
            #         await sql_replicator.synchronize(namespace, table)
            # except asyncio.TimeoutError as e:
            #     e.dap_table = table
            #     e.dap_namespace = namespace
            #     raise
            # except Exception as e:  # TODO seperate these so we don't drop if it fails to sync for a non timeout reason
            #     ## add table info so we can retry
            #     e.dap_table = table
            #     e.dap_namespace = namespace
            #     raise

        namespace = "canvas"

        ## I believe operation_name: "export" just refers to what will show up in the logs
        if operation == "init":
            await session.execute_operation_on_tables(namespace, table_names, "init", init_tables)
        elif operation == "sync":
            await session.execute_operation_on_tables(namespace, table_names, "sync", sync_tables)
            # TODO temporarily removing reinit fallback to see if fresh db fixes issue
            # try:
            #     await session.execute_operation_on_tables(namespace, table_names, "sync", sync_tables)
            #     ## retry by dropping and initing if sync fails
            # except BaseExceptionGroup as e:
            #     for exc in e.exceptions:    # #exceptions==#fails
            #         failed_table = getattr(exc, "dap_table", None)     # TODO this should be a string
            #         failed_namespace = getattr(exc, "dap_namespace", "canvas")

            #         ## sync failed, so drop and re-init # TODO email me if something happens
            #         if failed_table: # TODO what if canvas is down? We'll drop and fail to init
            #             print(f"Dropping and re-initing failed table: {failed_table}")
            #             await dropper.drop(failed_namespace, failed_table)
            #             await init_tables(failed_namespace, failed_table)
        else:
            raise ValueError(f"Error: Invalid operation: {operation}")

def validate_table_names(tables_str:str) -> str:
    allowed_tables = {
        "users", 
        "courses", 
        "enrollment_terms", 
        "assignments", 
        "submissions", 
        "enrollments", 
        "content_tags", 
        "context_modules"
    }

    if tables_str == "all":
        return ','.join(allowed_tables)

    tables_str = tables_str.lower().replace(" ", "")  # Remove any whitespace
    table_names = [t for t in tables_str.split(",") if t]  # Split and filter out empty strings

    for table in table_names:
        if table not in allowed_tables:
            print(f"Error: Invalid table name: {table}")
            sys.exit(2)

    return ','.join(table_names)

async def operate(operation:str, tables_str = "all"):
    tables_str = validate_table_names(tables_str)

    await init_or_sync_db_tables(tables_str, operation)

async def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    await operate(args.operation, args.table_name_s)

if __name__ == "__main__":
    asyncio.run(main())
