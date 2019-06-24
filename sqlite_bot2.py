# Work with Python 3.6
import discord
from discord.ext.commands import Bot

import sqlite3
from sqlite3 import Error

import time
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dateutil import parser
from matplotlib import style
style.use ('fivethirtyeight')

BOT_PREFIX = ("?", "!")
f = open("secret.txt", "r")
TOKEN = f.read()

client = Bot(command_prefix=BOT_PREFIX)
#testbedChannel = client.get_channel('585515464797716499');


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    try:
        conn = sqlite3.connect(db_file)
        print("connected to " + db_file);
        return conn
    except Error as e:
        print(e)
 
    return None


conn = create_connection("Fam Tracker")

def get_channel(channels, channel_name):
    for channel in client.get_all_channels():
        #print(channel)
        if channel.name == channel_name:
            return channel
    return None

@client.command(pass_context=True)
async def player(ctx, ppl : str):
    cur = conn.cursor()
    #cur.execute("SELECT * FROM test1 WHERE Name=?", str(ppl))
    cur.execute("SELECT * FROM (SELECT * FROM LVE UNION SELECT * FROM SCE UNION SELECT * FROM GLE UNION SELECT * FROM KILL UNION SELECT * FROM DKFT) WHERE Name=? ORDER BY Date DESC LIMIT 1", (ppl,))

    value_list = cur.fetchone()
    #msg = ''.join(str(v) for v in value_list)
    #msg = "The power of " + ppl + " is " + msg;
    msg = "**%s**\n  Last Updated: %s\n  Lv: %s\n  Power: %sk" % value_list 
    print(msg);

    #await client.say(msg)

    dates = []
    values = []

    cur.execute("SELECT * FROM (SELECT * FROM LVE UNION SELECT* FROM SCE UNION SELECT * FROM GLE UNION SELECT * FROM KILL UNION SELECT * FROM DKFT) WHERE Name=?", (ppl,))

    value_list = cur.fetchall()

    for row in value_list:
        #print("is this a date?:", row[1])
        dates.append(parser.parse(row[1]))
        values.append(row[3])


    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    line, = ax.plot(dates, values, lw=2)
    fig.autofmt_xdate()
    ax.set_title("Power of " + ppl)
    ax.set_xlabel("Date")
    ax.set_ylabel("Power (in thousands)")
    plt.savefig('latest.png', bbox_inches="tight")
    plt.close()

    #await client.send_file(testbedChannel, "latest.png")
    testbedChannel = get_channel(client.get_all_channels(), 'testbed')
    await client.send_file(ctx.message.channel, "latest.png", content=msg)

@client.command(pass_context=True)
async def players(ctx, *argv):
    args = [];
    for arg in argv:
        args.append(arg)

    cur = conn.cursor()

    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    for i in range(len(argv)):
        cur.execute("SELECT Date, Power FROM (SELECT * FROM LVE UNION SELECT* FROM SCE UNION SELECT * FROM GLE UNION SELECT * FROM KILL UNION SELECT * FROM DKFT) WHERE Name=?", (argv[i],))
        value_list = cur.fetchall()
        dates = []
        values = []
        for row in value_list:
            dates.append(parser.parse(row[0]))
            values.append(row[1])
        line, = ax.plot(dates, values, lw=2, label=argv[i])

    fig.autofmt_xdate()
    ax.set_title("Power of " + str(len(argv)) + " Players")
    ax.set_xlabel("Date")
    ax.set_ylabel("Power (in thousands)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.savefig('latest.png', bbox_inches="tight")
    plt.close()

    testbedChannel = get_channel(client.get_all_channels(), 'testbed')
    await client.send_file(ctx.message.channel, "latest.png")

@client.command(pass_context=True)
async def alliance(ctx, name):
    cur = conn.cursor()
    #cur.execute("SELECT * FROM test1 WHERE Name=?", str(ppl))
    cmd = "SELECT Date, count(*), SUM(Power) FROM " + name + " GROUP BY Date ORDER BY Date DESC LIMIT 1"
    cur.execute(cmd)

    value_list = cur.fetchone()
    #msg = ''.join(str(v) for v in value_list)
    #msg = "The power of " + ppl + " is " + msg;
    msg = "**" + name + "**\n  Last Updated: %s\n  Number of Players: %s\n  Total Power: %sk" % value_list 
    print(msg);

    #await client.say(msg)

    dates = []
    values = []

    cmd = "SELECT Date, SUM(Power) FROM " + name + " GROUP BY Date ORDER BY Date"
    cur.execute(cmd)

    value_list = cur.fetchall()

    for row in value_list:
        #print("is this a date?:", row[1])
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

    #await client.send_file(testbedChannel, "latest.png")
    testbedChannel = get_channel(client.get_all_channels(), 'testbed')
    await client.send_file(ctx.message.channel, "latest.png", content=msg)

@client.command(pass_context=True)
async def alliances(*argv):
    args = [];
    for arg in argv:
        args.append(arg)

    cur = conn.cursor()

    fig = plt.figure()
    plt.style.use('dark_background')
    ax = fig.add_subplot(111)
    for i in range(len(argv)):
        cur.execute("SELECT Date, SUM(Power) FROM " + argv[i] + " GROUP BY Date ORDER BY Date")
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

    testbedChannel = get_channel(client.get_all_channels(), 'testbed')
    await client.send_file(ctx.message.channel, "latest.png")

@client.event
async def on_ready():
    print("Logged in as " + client.user.name)


client.run(TOKEN)
