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
from datetime import timedelta
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
@bot.command(brief="Plot the growth of a player", description="Plot the growth of a single player. To compare the growth of different players, use the \"players\" command", aliases=["plot", "plot-one"])
async def player(ctx, ppl : str):
    cur = conn.cursor()

    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(ppl.lower())
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    res = cur.fetchone()
    key = -1
    if res is None or len(res) == 0:
        msg = "**[WARNING]** The player " + ppl + " does not exist. Please check your spelling and try again."
        logging.warning(msg)
        await ctx.send(msg)
        return
    else:
        key = res[0]
    #cur.execute("SELECT * FROM test1 WHERE Name=?", str(ppl))
    sql1 = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}" ORDER BY ROWID DESC LIMIT 1'''.format(str(key))
    logging.debug("SQL: " + sql1)
    cur.execute(sql1)

    value_list = cur.fetchone()
    if value_list is None or len(value_list) == 0:
        msg = "**[WARNING]** The player " + ppl + " does not have any data."
        logging.warning(msg)
        await ctx.send(msg)
        return

    sql2 = '''SELECT name FROM display WHERE key="{}" ORDER BY ROWID DESC LIMIT 1'''.format(str(key))
    logging.debug("SQL: " + sql2)
    cur.execute(sql2)
    default_name = cur.fetchone()

    title = ppl;
    alias_list = [];
    if default_name is not None:
        if (default_name[0].lower() == ppl.lower()):
            title = default_name[0];
        else:
            alias_list.append(default_name[0].lower())

    sql3 = '''SELECT name FROM alias WHERE key="{}" ORDER BY ROWID DESC'''.format(str(key))
    logging.debug("SQL: " + sql3)
    cur.execute(sql3)
    list_o_names = cur.fetchall()
    if list_o_names is not None:
        if (list_o_names[0][0].lower() != title.lower() and list_o_names[0][0] not in alias_list):
            alias_list.append(list_o_names[0][0])
        if (list_o_names[-1][0].lower() != title.lower() and list_o_names[-1][0] not in alias_list):
            alias_list.append(list_o_names[-1][0])
        if (len(list_o_names) > 2 and list_o_names[-2][0].lower() != title.lower() and list_o_names[-2][0] not in alias_list):
            alias_list.append(list_o_names[-2][0])
    alias_string = ", ".join(alias_list)
    if (len(list_o_names) > 4):
        alias_string += "... (+%s more)" % (len(list_o_names) - len(alias_list) - 1)
    #else:
        #print("list_o_names is %d long" % len(list_o_names))
    if (len(alias_list) > 0):
        alias_string = "\n  Also known as: " + alias_string

    #msg = ''.join(str(v) for v in value_list)
    #msg = "The power of " + ppl + " is " + msg;
    msg = "**%s**\n  Last Updated: %s\n  Lv: %s\n  Power: %s" % (title, value_list[0], value_list[1], '{:,}'.format(value_list[2]))

    # get growth rates:
    sql4 = '''SELECT Lv, Power, Date FROM LVE WHERE PlayerKey="{}" AND Date>"{}" ORDER BY DATE DESC'''.format(str(key), datetime.datetime.now() - datetime.timedelta(days=8))
    logging.debug('SQL: ' + sql4)
    cur.execute(sql4)
    result = cur.fetchall()
    if result is not None and len(result) > 3:
        num_entries = len(result)
        power_change = result[0][1] - result[-1][1]
        growth_per_day = float(power_change) / num_entries
        growth_per_week = growth_per_day * 7
        percent_growth_per_week = growth_per_week / result[-1][1]
        msg += "\n  Growth: %s (%s) per week" % (human_format(growth_per_week), '{:.2%}'.format(percent_growth_per_week))

    msg += alias_string;

    # get lve fam birthday
    sql5 = '''
        SELECT Date, Lv
        FROM [LVE] A
        INNER JOIN
        (
            SELECT Alliance, MIN(Date) AS minDate
            FROM [LVE]
            GROUP BY Alliance
        ) B ON A.Alliance = B.Alliance
        INNER JOIN
        (
            SELECT PlayerKey, MIN(Date) AS minDate
            FROM [LVE]
            GROUP BY PlayerKey
        ) C ON
            A.PlayerKey="{}" AND
            A.PlayerKey = C.PlayerKey AND
            julianday(B.minDate, '+2 days') < julianday(C.minDate) AND
            A.Date = C.minDate
    '''.format(str(key))
    logging.debug("SQL: " + sql5)
    cur.execute(sql5)
    birthday = cur.fetchone()
    if (birthday is not None):
        msg += "\n  LVE Birthday: joined on %s when lv %d" % (birthday[0], birthday[1])



    logging.info(msg)


    dates = []
    values = []

    sql = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}" AND julianday(Date, '+1 month') > julianday('now', 'localtime') '''.format(str(key))
    logging.debug("SQL: " + sql)
    cur.execute(sql)

    value_list = cur.fetchall()

    for row in value_list:
        dates.append(parser.parse(row[0]))
        values.append(row[2])

    async with ctx.message.channel.typing():
        fig = plt.figure()
        plt.style.use('dark_background')
        ax = fig.add_subplot(111)
        line, = ax.plot(dates, values, lw=2)
        fig.autofmt_xdate()
        ax.set_title("Growth of " + ppl + " for this Month")
        ax.set_xlabel("Date")
        ax.set_ylabel("Power")
        ax.get_yaxis().set_major_formatter(
            tkr.FuncFormatter(lambda x, p: format(int(x), ',')))
        plt.savefig(img_save_name, bbox_inches="tight")
        plt.close()

    await ctx.send(msg, file=discord.File(img_save_name))

@bot.command(brief="Plot the growth of multiple players", description="Plot the growth of the specified players on a single graph", aliases=["players", "plot-many", "plot-several", "plot-multiple", "plot-players"])
async def compare(ctx, *argv):
    args = [];
    for arg in argv:
        args.append(arg)

    cur = conn.cursor()

    async with ctx.message.channel.typing():
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
            if res is None:
                msg = "**[WARNING]** The player " + ppl + " does not exist. Please check your spelling and try again."
                logging.warning(msg)
                await ctx.send(msg)
                continue
            else:
                key = res[0]
            sql = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}" AND julianday(Date, '+1 month') > julianday('now', 'localtime')'''.format(str(key))
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
        ax.set_title("Power of " + str(len(argv)) + " Players this Month")
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
'''
@bot.command(brief="Plot the growth of all players in an alliance", description="Plot the growth of all players in an alliance within an optionally specified level range on a single graph", aliases=["plot-alliance", "plot-all"])
async def alliance(ctx, team : str, min=1,  max=40):

    cur = conn.cursor()

    sql = '''SELECT PlayerKey FROM LVE WHERE Alliance="{}" AND Date>date("now","-2 days") AND Lv>="{}" AND Lv <="{}" GROUP BY PlayerKey ORDER BY Power DESC'''.format(team.lower(), str(min), str(max))
    logging.debug('SQL: ' + sql)
    cur.execute(sql)
    query_res = cur.fetchall()

    if query_res is None or len(query_res) == 0:
        msg = "**[WARNING]** No results found for team {}".format(team)
        logging.warning(msg)
        await ctx.send(msg)
        return

    async with ctx.message.channel.typing():
        fig = plt.figure()
        plt.style.use('dark_background')
        ax = fig.add_subplot(111)
        for key in query_res:
            sql3 = '''SELECT name FROM display WHERE key="{}" ORDER BY ROWID DESC LIMIT 1'''.format(key[0])
            logging.debug('SQL: ' + sql3)
            cur.execute(sql3)
            get_name = cur.fetchone()

            if not get_name:
                sql3 = '''SELECT Name FROM alias WHERE key="{}" ORDER BY ROWID DESC LIMIT 1'''.format(key[0])
                logging.debug('SQL: ' + sql3)
                cur.execute(sql3)
                get_name = cur.fetchone()
            sql = '''SELECT Date, Lv, Power FROM LVE WHERE PlayerKey="{}" AND julianday(Date, '+1 month') > julianday('now', 'localtime')'''.format(str(key[0]))
            logging.debug("SQL: " + sql)
            cur.execute(sql)
            value_list = cur.fetchall()
            dates = []
            values = []
            for row in value_list:
                dates.append(parser.parse(row[0]))
                values.append(row[2])
            line, = ax.plot(dates, values, lw=2, label=get_name[0])

        fig.autofmt_xdate()
        ax.set_title("Power of " + str(len(query_res)) + " Players this Month")
        ax.set_xlabel("Date")
        ax.set_ylabel("Power")
        ax.get_yaxis().set_major_formatter(
            tkr.FuncFormatter(lambda x, p: format(int(x), ',')))
        plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
        plt.savefig(img_save_name, bbox_inches="tight")
        plt.close()

    await ctx.send(file=discord.File(img_save_name))

def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    # add more suffixes if you need them
    return '%.2f%s' % (num, ['', 'k', 'M', 'G', 'T', 'P'][magnitude])

@bot.command(brief="Assign a display name", description="Designate the case-sensitive display name of a player", aliases=["make-default", "set-default", "make-name", "set-name", "make-display", "set-display"])
async def name(ctx, name : str):
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}" ORDER BY ROWID DESC LIMIT 1'''.format(name.lower())
    logging.debug('SQL: ' + sql)
    cur.execute(sql)
    key = cur.fetchone()

    if not key:
        msg = "**[ERROR]** The name {} does not exist. Try adding it first by doing !add".format(name)
        logging.error(msg)
        await ctx.send(msg)
        return

    sql = '''DELETE FROM display WHERE key="{}"'''.format(key[0])
    logging.debug('SQL: ' + sql)
    cur.execute(sql)

    sql = '''INSERT INTO display (key, name) VALUES ("{}", "{}")'''.format(key[0], name)
    logging.debug('SQL: ' + sql)
    cur.execute(sql)

    conn.commit()

    msg = 'Set \'' + name + '\' as the player display name'
    logging.info(msg)
    await ctx.send(msg)


@bot.command(brief="Display the roster", description="Display the roster with active/inactive status for the given team")
async def roster(ctx, team : str, options='-g'):
    '''
        COMMAND OPTIONS:
        -n or -a   = sort my name/alphabetically
        -p         = sort by power
        -g         = sort by growth
    '''
    num_insufficient = 0;
    num_active = 0;
    num_inactive = 0;
    total_growth = 0;
    total_percent_growth = 0;
    roster_msg = "";
    cur = conn.cursor()


    sql = '''SELECT PlayerKey FROM LVE WHERE Alliance="{}" AND Date>date("now","-2 days") GROUP BY PlayerKey'''.format(team.lower())
    '''if options == "-n" or options == "-a":
        # DON'T KNOW HOW TO IMPLEMENT THIS YET
    elif (options == "-p"):
        sql += " ORDER BY Power DESC"
    elif (options == "-g"):
        # NOT SURE KNOW HOW TO IMPLEMENT THIS YET'''
    sql += " ORDER BY Power DESC"
    logging.debug('SQL: ' + sql)
    cur.execute(sql)
    query_res = cur.fetchall()

    async with ctx.message.channel.typing():

        for key in query_res:
            sql2 = '''
                SELECT Power, Date
                FROM [LVE] A
                WHERE PlayerKey="{}"
                AND Power NOT IN (
                    SELECT Power
                    FROM (
                        SELECT MAX(Date) AS max, Power
                        FROM [LVE] B
                        WHERE B.PlayerKey = A.PlayerKey
                        )
                    )
                ORDER BY Date DESC
                LIMIT 1
            '''.format(key[0])
            logging.debug('SQL: ' + sql2)
            cur.execute(sql2)
            recent = cur.fetchone()

            sql3 = '''SELECT name FROM display WHERE key="{}" ORDER BY ROWID DESC LIMIT 1'''.format(key[0])
            logging.debug('SQL: ' + sql3)
            cur.execute(sql3)
            get_name = cur.fetchone()

            if not get_name:
                sql3 = '''SELECT Name FROM alias WHERE key="{}" ORDER BY ROWID DESC LIMIT 1'''.format(key[0])
                logging.debug('SQL: ' + sql3)
                cur.execute(sql3)
                get_name = cur.fetchone()

            sql4 = '''SELECT Lv, Power, Date FROM LVE WHERE PlayerKey="{}" AND Date>"{}" ORDER BY DATE DESC'''.format(key[0], datetime.datetime.now() - datetime.timedelta(days=8))
            logging.debug('SQL: ' + sql4)
            cur.execute(sql4)
            result = cur.fetchall()

            num_entries = len(result)

            if num_entries < 3:
                # Case insufficent data
                msg = "```🆕 Name: {:25}| Level: {:<3}| Power: {:<8}| Insufficient data, only {} entries this week ```".format( get_name[0] , result[0][0], human_format(result[0][1]), num_entries)
                num_insufficient += 1

            elif recent and ( datetime.datetime.strptime(recent[1], "%Y-%m-%d") + datetime.timedelta(days=14) ) >=  datetime.datetime.now() :
                # Case active
                power_change = result[0][1] - result[-1][1]
                growth_per_day = float(power_change) / num_entries
                growth_per_week = growth_per_day * 7
                #percent_growth_per_day = growth_per_day /  recent[0];
                percent_growth_per_week = growth_per_week / result[-1][1]

                msg = "```🌿 Name: {0:<25}| Level: {1:<3}| Power: {2:<8}| Active, growing {3} ({4:.2%}) per week ```".format( get_name[0] , result[0][0], human_format(result[0][1]), human_format(growth_per_week), percent_growth_per_week)
                num_active += 1
                total_growth += growth_per_week
                total_percent_growth += percent_growth_per_week

            else :
                # Case inactive
                last_seen = ""
                if (recent):
                    last_seen = recent[1]
                else:
                    last_seen = "never"
                msg = "```🕒 Name: {:<25}| Level: {:<3}| Power: {:<8}| Inactive, last seen {} ```".format( get_name[0], result[0][0], human_format(result[0][1]), last_seen)
                num_inactive += 1

            #roster_msg += msg + "\n"
            logging.info(msg)
            await ctx.send(msg)

    num_players = num_active + num_inactive + num_insufficient
    if num_players == 0:
        msg = "No data has been uploaded for team {} today".format(team)
        logging.info(msg)
        await ctx.send(msg)
        return
    #overview_msg = "active players {} out of {}\n".format(num_active + num_insufficient, num_players)
    #overview_msg += "the average member grows {0} ({1:.2f}%) per week\n".format(human_format(total_growth/num_players), total_percent_growth/num_players)
    #overview_msg += "the average active member grows {} ({}%} per week".format(total_growth/num_players, total_percent_growth/num_players)
    embed=discord.Embed(title="Team {} Summary".format(team.upper()), color=0x00ff00)
    #embed.add_field(name="OVERVIEW", value=overview_msg, inline=False)
    #embed.add_field(name="ROSTER ({}):".format(num_players), value=roster_msg, inline=False)
    embed.add_field(name="Player Count ({})".format(num_players), value='''{} Active, {} Inactive, {} New'''.format(num_active, num_inactive, num_insufficient), inline=False)
    embed.add_field(name="Weekly Growth", value='''{0} ({1:.2f}%) per Player'''.format(human_format(total_growth/num_players), total_percent_growth/num_players), inline=False)
    await ctx.send("Done.", embed=embed)



@bot.event
async def on_ready():
    logging.info("Logged in as " + bot.user.name)

@bot.event
async def on_command_error(ctx, error):
    msg = "**[ERROR]** %s" % (error)
    logging.error(msg)
    await ctx.send(msg)
    raise

# ------------------------------------------------------------------------------
#                                 MAIN SCRIPT
# ------------------------------------------------------------------------------
init_logger()
style.use ('fivethirtyeight')
f = open(token_file, "r")
TOKEN = f.read()
bot.run(TOKEN)
