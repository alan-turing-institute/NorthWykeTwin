"""
Useful database-related functions for predictive models
"""

import logging
import sys
import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from dtbase.core.db import connect_db, session_open, session_close

from dtbase.core.constants import SQL_CONNECTION_STRING, SQL_DBNAME

logger = logging.getLogger(__name__)


def get_sqlalchemy_session(connection_string=None, dbname=None):
    """
    For other functions in this module, if no session is provided as an argument,
    they will call this to get a session using default connection string.
    """
    if not connection_string:
        connection_string = SQL_CONNECTION_STRING
    if not dbname:
        dbname = SQL_DBNAME
    status, log, engine = connect_db(connection_string, dbname)
    session = session_open(engine)
    return session


def print_rows_head(rows, numrows=0):
    logging.info("Printing:{0} of {1}".format(numrows, len(rows)))
    if numrows == 0:
        for row in rows[: len(rows)]:
            logging.info(row)
    else:
        for row in rows[:numrows]:
            logging.info(row)
