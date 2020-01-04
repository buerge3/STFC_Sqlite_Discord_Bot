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

def rm_duplicates():
	sql = '''SELECT (name, key) FROM alias WHERE name REGEXP "[A-Z]"'''
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    name_list = cur.fetchall()
    for i in range(len(name_list)):
    	sql = '''SELECT key FROM alias WHERE name="{}"'''.format(name_list[i][0])
    	logging.debug("SQL: " + sql)
    	cur.execute(sql)
    	val_list = cur.fetchall()
    	if val is not None:
    		for k in range(len(val_list)):
    			sql = '''UPDATE LVE SET PlayerKey="{}" WHERE name="{}" AND PlayerKey="{}"'''.format(val_list[k], name_list[i][0], name_list[i][1])
    			logging.debug("SQL: " + sql)
    			cur.execute(sql)

