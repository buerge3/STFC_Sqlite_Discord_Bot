#!/usr/bin/env python3
#
# FILENAME: plotty-bot.py
# CREATED:  August 17, 2019
# AUTHOR:   buerge3
#
# A discord bot for plotting player and alliance growth
# Usage: "python3 ./plotty-bot.py
import discord
from discord.ext import commands
from discord import Status
#from discord.ext.commands import Bot

import sqlite3
from sqlite3 import Error

import logging

import time
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as tkr
from dateutil import parser
from matplotlib import style

# MODIFIABLE PARAMTERS
db_name = "LVE.db"
token_file = "secret_plotty.txt"
img_save_name = "latest-plotty.png"
BOT_PREFIX = ("!","?")
bot = commands.Bot(command_prefix=BOT_PREFIX)

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


# -----------------------------------------------------------------------------
#                                    FUNCTIONS
# -----------------------------------------------------------------------------
# init_logger
# initialize the logger to output msgs of lv INFO or higher to the console,
# and write messages of DEBUG or higher to a log file
def init_logger():
    logfile_name = datetime.datetime.now().strftime("%d-%m-%Y_%I-%M-%S_%p")
    #logging.basicConfig(filename='logs/'+logfile_name, filemode='w', format='[%(asctime)s] %(levelname)s: %(message)s')
    logFormatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)
    fileHandler = logging.FileHandler("{}/{}.log".format('logs', logfile_name))
    fileHandler.setFormatter(logFormatter)
    fileHandler.setLevel(logging.DEBUG)
    rootLogger.addHandler(fileHandler)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    consoleHandler.setLevel(logging.WARNING)
    rootLogger.addHandler(consoleHandler)


# -----------------------------------------------------------------------------
#                     DISCORD BOT COMMANDS & EVENTS
# -----------------------------------------------------------------------------
@bot.command(description="Plot the growth of a single player. To compare the growth of different players, use the \"players\" command")
async def player(ctx, ppl : str):
    cur = conn.cursor()

    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(ppl.lower())
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    res = cur.fetchone()
    key = -1
    if res is None:
        msg = "The player " + ppl + " does not exist. Please check your spelling and try again."
        logging.warning(msg)
        await ctx.send(msg)
        return
    else:
        key = res[0]
    #cur.execute("SELECT * FROM test1 WHERE Name=?", str(ppl))
    sql = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}" ORDER BY ROWID DESC LIMIT 1'''.format(str(key))
    logging.debug("SQL: " + sql)
    cur.execute(sql)

    value_list = cur.fetchone()
    #msg = ''.join(str(v) for v in value_list)
    #msg = "The power of " + ppl + " is " + msg;
    msg = "**%s**\n  Last Updated: %s\n  Lv: %s\n  Power: %s" % (ppl, value_list[0], value_list[1], '{:,}'.format(value_list[2]))
    logging.info(msg)

    dates = []
    values = []

    sql = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}" AND julianday(Date, '+14 days') > julianday('now') '''.format(str(key))
    logging.debug("SQL: " + sql)
    cur.execute(sql)

    value_list = cur.fetchall()

    for row in value_list:
        dates.append(parser.parse(row[0]))
        values.append(row[2])


    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    line, = ax.plot(dates, values, lw=2)
    fig.autofmt_xdate()
    ax.set_title("Growth of " + ppl + " for Two Weeks")
    ax.set_xlabel("Date")
    ax.set_ylabel("Power")
    ax.get_yaxis().set_major_formatter(
        tkr.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.savefig(img_save_name, bbox_inches="tight")
    plt.close()

    await ctx.send(msg, file=discord.File(img_save_name))

@bot.command(description="Plot the growth of multiple players")
async def players(ctx, *argv):
    args = [];
    for arg in argv:
        args.append(arg)

    cur = conn.cursor()

    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    for i in range(len(argv)):
        ppl = argv[i]
        key = -1
        sql = '''SELECT key FROM alias WHERE name="{}"'''.format(ppl.lower())
        logging.debug("SQL: " + sql)
        cur.execute(sql)
        res = cur.fetchone()
        key = -1
        if res is None:
            msg = "The player " + ppl + " does not exist. Please check your spelling and try again."
            logging.warning(msg)
            await ctx.send(msg)
            return
        else:
            key = res[0]
        sql = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}"'''.format(str(key))
        logging.debug("SQL: " + sql)
        cur.execute(sql)
        value_list = cur.fetchall()
        dates = []
        values = []
        for row in value_list:
            dates.append(parser.parse(row[0]))
            values.append(row[2])
        line, = ax.plot(dates, values, lw=2, label=argv[i])

    fig.autofmt_xdate()
    ax.set_title("Power of " + str(len(argv)) + " Players")
    ax.set_xlabel("Date")
    ax.set_ylabel("Power")
    ax.get_yaxis().set_major_formatter(
        tkr.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.savefig(img_save_name, bbox_inches="tight")
    plt.close()

    await ctx.send(file=discord.File(img_save_name))

'''
@bot.command(description="Plot the growth of a single alliance. To compare the growth of different alliances, use the \"alliances\" command")
async def alliance(ctx, name):
    cur = conn.cursor()
    #cur.execute("SELECT * FROM test1 WHERE Name=?", str(ppl))
    cmd = "SELECT Date, count(*), SUM(Power) FROM LVE WHERE alliance=" + name + " GROUP BY Date ORDER BY Date DESC LIMIT 1"
    cur.execute(cmd)

    value_list = cur.fetchone()
    #msg = ''.join(str(v) for v in value_list)
    #msg = "The power of " + ppl + " is " + msg;
    msg = "**" + name + "**\n  Last Updated: %s\n  Number of Players: %s\n  Total Power: %sk" % value_list 
    logging.info(msg);

    dates = []
    values = []

    cmd = "SELECT Date, SUM(Power) FROM LVE WHERE alliance=" + name + " GROUP BY Date ORDER BY Date"
    cur.execute(cmd)

    value_list = cur.fetchall()

    for row in value_list:
        dates.append(parser.parse(row[0]))
        values.append(row[1])


    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    line, = ax.plot(dates, values, lw=2)
    fig.autofmt_xdate()
    ax.set_title("Power of " + name)
    ax.set_xlabel("Date")
    ax.set_ylabel("Power (in thousands)")
    plt.savefig('latest.png', bbox_inches="tight")
    plt.close()

    await ctx.send(content=msg, file=discord.File(img_save_name))

@bot.command(description="Plot the growth of multiple alliances in one chart")
async def alliances(*argv):
    args = [];
    for arg in argv:
        args.append(arg)

    cur = conn.cursor()

    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    for i in range(len(argv)):
        cur.execute("SELECT Date, SUM(Power) FROM LVE WHERE alliance=" + argv[i] + " GROUP BY Date ORDER BY Date")
        value_list = cur.fetchall()
        dates = []
        values = []
        for row in value_list:
            dates.append(parser.parse(row[0]))
            values.append(row[1])
        line, = ax.plot(dates, values, lw=2, label=argv[i])

    fig.autofmt_xdate()
    ax.set_title("Power of " + str(len(argv)) + " Alliances")
    ax.set_xlabel("Date")
    ax.set_ylabel("Power (in thousands)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.savefig('latest.png', bbox_inches="tight")
    plt.close()

    await ctx.send(file=discord.File(img_save_name))

@bot.event
async def on_ready():
    logging.info("Logged in as " + bot.user.name)
'''

# ------------------------------------------------------------------------------
#                                 MAIN SCRIPT
# ------------------------------------------------------------------------------
init_logger()
style.use ('fivethirtyeight')
f = open(token_file, "r")
TOKEN = f.read()
bot.run(TOKEN)
