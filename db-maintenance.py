#!/usr/bin/env python3
#
# FILENAME: db-maintenance.py
# CREATED:  October 17, 2019
# AUTHOR:   buerge3
#
# A discord bot for performing various maintenance and
# corrective actions on the LVE database
# Usage: "python3 ./db-maintenance.py <flags>
import sys
import sqlite3

# MODIFIABLE PARAMTERS
db_name = "LVE.db"

# -----------------------------------------------------------------------------
#                        DATABASE CONNECTION SCRIPT
# -----------------------------------------------------------------------------
def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    try:
        conn = sqlite3.connect(db_file)
        logging.info("connected to " + db_file);
        return conn
    except Error as e:
        logging.error(e, exc_info=True)
 
    return None


conn = create_connection(db_name)