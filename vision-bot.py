#!/usr/bin/env python3
#
# FILENAME: vision-bot.py
# CREATED:  August 17, 2019
# AUTHOR:   buerge3
#
# A discord bot for uploading STFC roster image data to a database
# Usage: "python3 ./vision-test.py
import discord
from discord.ext import commands
from discord import Status

import sqlite3
from sqlite3 import Error

from PIL import Image
import pytesseract
import math
from spellchecker import SpellChecker

import aiohttp
import aiofiles

import datetime
import re

import logging

# MODIFIABLE PARAMETERS
db_name = "LVE.db"
token_file = "secret_vision.txt"
x_percent = 14
bot = commands.Bot(command_prefix='!')

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
# add_name_to_alias
# @param name, the name to add to the alias table
def add_name_to_alias(name):
    cur = conn.cursor()
    sql = '''SELECT value FROM __state WHERE name="key"'''
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    key = cur.fetchone()[0]
    sql = '''INSERT INTO alias (key, name) VALUES ("{}", "{}")'''.format(key, name.lower())
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    new_key = int(key) + 1
    sql = '''UPDATE __state SET value={} WHERE name="key"'''.format(new_key)
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    return key

async def add_name_to_dict(ctx, new_name):
    # add incorrect name to dictionary
    file = open("STFC_dict.txt", "a")
    file.write(new_name + "\n")
    #add_name_to_alias(old_name)
    msg = 'Added \'' + new_name+ '\' to the dictionary'
    logging.info(msg)
    await ctx.send(msg)

# IsImage
# @return true if the first command-line argument is an image
def isImage(context, num):
    pic_ext = ['.jpg','.png','.jpeg']
    for ext in pic_ext:
        if context.message.attachments[num].filename.endswith(ext):
            return True
    return False

# getImage
# @param url, a url to an image
# fetch the image at the specified url and save it as 'latest.jpg'
async def getImage(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            f = await aiofiles.open('latest.jpg', mode='wb')
            await f.write(await resp.read())
            await f.close()

# get_rgb_filter
# @param im, the STFC roster screenshot to find appropriate filter values for
# @returns rgb, a three-element list consisting of the rgb values for the filter
def get_rgb_filter(im):
    width, height = im.size
    rgb = [220, 220, 220]
    for i in range(3):
        im_rgb = im.crop((0, 0, width, math.floor(height/10)))
        #logging.debug("trying r=" + str(rgb[0]), ", g=" + str(rgb[1]) + ", b=" + str(rgb[2]))
        apply_img_mask(im_rgb, rgb, x_percent)
        word = pytesseract.image_to_string(im_rgb)
        logging.debug("I read: " + word)
        if (bool(re.match(r"MEM", word))):
            logging.debug("found a working filter!")
            return rgb;
        else:
            rgb[0] -= 20
            rgb[1] -= 20
            rgb[2] -= 20
    return None

# apply_img_mask
# @param im, the image to apply a mask to
# @param rgb, a three-element list consisting of the rgb values for the mask threshold
# @param x_percent, what percentage of the width to crop off from the right. Used to
#        remove STFC rank symbols for premier, commodore, etc
def apply_img_mask(im, rgb, x_percent):
    pixdata = im.load()
    width, height = im.size
    x_cutoff = math.floor(width / x_percent)
    for x in range(width):
        for y in range(height):
            r,g,b = im.getpixel((x,y))
            if r < rgb[0] or g < rgb[1] or b < rgb[2] or x < x_cutoff:
                #out.putpixel((x,y), 0)
                pixdata[x,y] = (255, 255, 255);
            else:
                pixdata[x,y] = (0,0,0,0)

# process_image
# @param im, an STFC roster screenshot
# @param names_list, an empty list to populate with player names
# @param level_list, an empty list to populate with player levels
# @return True if success, False if an error occurred
async def process_image(ctx, im, names_list, level_list):
    width, height = im.size
    im_names = im.crop((0, math.floor(height/10), math.floor(width/2), height))
    names = pytesseract.image_to_string(im_names)
    tmp_list = names.replace("|", "").split('\n\n')
    success = False
    __flag = False
    for tmp in tmp_list:
        if (bool(re.match(r"^[0-9]+ \S", tmp))):
            lv, name = tmp.split(' ', 1)
            level_list.append(lv)
            names_list.append(name)
            success = True
        elif (bool(re.match(r"^[0-9]+$", tmp))):
            level_list.append(tmp)
            __flag = True
        elif (__flag):
            names_list.append(tmp)
            success = True
        else:
            names_list.append("DELETE_ME")
            level_list.append(0)
    if not success:
        msg = "Unable to process image, please try again."
        logging.error(msg)
        await ctx.send(msg)
        return False;
    if len(names_list) != len(level_list):
        msg = "Unable to process image; cause: did not identify exactly one level for each name"
        logging.error(msg)
        logging.debug("NAMES:")
        for name in names_list:
            logging.debug(name)
        logging.debug("LEVELS:")
        for lv in level_list:
            print(lv)
        return False;
    return True;

# check_spelling
# @param names_list, a list of player names to check the spelling of
#         using the dictionary file 'STFC_dict.txt'
async def check_spelling(ctx, names_list):
    spell = SpellChecker(language=None, case_sensitive=False)
    spell.word_frequency.load_text_file("STFC_dict.txt")
    
    for i in range(len(names_list)):
        if (names_list[i] == "DELETE_ME"):
            continue
        word = names_list[i].lower()

        if word in spell:
            names_list[i] = word
            logging.debug(word + " is spelled correctly!")
        else:
            cor = spell.correction(word)
            if (cor != word):
                logging.debug("Corrected '{}' to '{}'".format(word, cor))
                names_list[i] = cor;
            else:
                msg = "Unrecognized player name {} in row {}. If this is a new player, please add them to the dictionary by doing '!add <player name>'".format(word, i)
                logging.warning(msg)
                await ctx.send(msg)
                names_list[i] = "DELETE_ME" + names_list[i]
                continue

# store_in_db
# @param names_list, a list of player names
# @param lv_list, a list of player levels
# @param power_list, a list of player power
# @param which alliance the roster screenshot belongs to
async def store_in_db(ctx, names_list, lv_list, power_list, team):

    cur = conn.cursor()

    # Store the data for each name in the database
    for i in range(0, len(names_list)):
        target = ""
        if "DELETE_ME" in names_list[i]:
            target="backlog"
            names_list[i] = names_list[i][9:] # remove "DELETE_ME" from the name string
        else:
            target="LVE"

        if (names_list[i] == ""):
            continue
        if i < len(lv_list) and i < len(power_list):
            sql = '''SELECT key FROM alias WHERE name="{}"'''.format(names_list[i].lower());
            logging.debug('SQL: ' + sql)
            cur.execute(sql)
            value_list = cur.fetchone()
            key = -1
            if value_list is None:
                key = add_name_to_alias(names_list[i])
            else:
                key = value_list[0]

            sql = '''SELECT * FROM LVE WHERE PlayerKey={} AND Date="{}"'''.format(key, datetime.datetime.now().strftime("%Y-%m-%d"))
            logging.debug("SQL: " + sql)
            cur.execute(sql)
            value_list = cur.fetchone()
            if value_list is not None:
                err_msg = "Data for player {} has already been entered today. Skipping this player...".format(names_list[i])
                logging.warning(err_msg)
                await ctx.send(err_msg)
                continue
            try:
                if (target == "LVE"):
                    sql = '''INSERT INTO {} (PlayerKey, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(target, key,
                        datetime.datetime.now().strftime("%Y-%m-%d"),
                        team,
                        int(lv_list[i]),
                        int(str(power_list[i]).replace(',', '')))
                    logging.debug("SQL: " + str(sql))
                    cur.execute(sql)
                else:
                    #sql = '''INSERT INTO {} (Name, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(target, names_list[i],
                    #    datetime.datetime.now().strftime("%Y-%m-%d"),
                    #    team,
                    #    int(lv_list[i]),
                    #    int(power_list[i].replace(',', '')))
                    await store_in_backlog((names_list[i], datetime.datetime.now().strftime("%Y-%m-%d"), team, int(lv_list[i]), int(power_list[i].replace(',', ''))))
                
            except ValueError:
                err_msg = "Cannot interpret the power of player " + names_list[i] + " as an integer."
                logging.warning(err_msg, exc_info=True)
                await ctx.send(err_msg)
                continue

            if target == "LVE":
                msg = "Name: " + names_list[i] + ",\tLv: " + str(lv_list[i]) + ",\tPower: " + str(power_list[i])
                logging.info(msg)
                await ctx.send(msg)
    conn.commit()

# func_alias
# @param ctx, Discord msg context
# @param new_name, player name string
# @param old_name, player name string
async def func_alias(ctx, new_name, old_name):
    logging.debug("Player " + str(ctx.message.author) + " running command \'alias\'")

    # add incorrect name to dictionary
    await add_name_to_dict(ctx, incorrect_name_spelling)

    # add alias
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(old_name.lower())
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    if value_list is None:
        #add_name_to_alias(args[0])
        msg = "[ERROR] The player \"" + old_name + "\" does not exist. Please add an alias using the format !alias <new_name> <old_name>"
        logging.error(msg)
        await ctx.send(msg)
    else:
        old_name_key = value_list[0]
        # check if the new name already exists in the database
        sql = '''SELECT key FROM alias WHERE name="{}"'''.format(new_name.lower())
        logging.debug("SQL: " + sql)
        cur.execute(sql)
        value_list_2 = cur.fetchone()
        if value_list_2 is None:
            sql = '''INSERT INTO alias (key, name) VALUES ("{}", "{}")'''.format(old_name_key, new_name.lower())
            logging.debug("SQL: " + sql)
            cur.execute(sql)
        else:
            new_name_key = value_list_2[0]
            sql = '''UPDATE alias SET key={} WHERE key="{}"'''.format(old_name_key, new_name_key)
            logging.debug("SQL: " + sql)
            cur.execute(sql)
            sql = '''UPDATE LVE SET PlayerKey={} WHERE PlayerKey="{}"'''.format(old_name_key, new_name_key)
            logging.debug("SQL: " + sql)
            cur.execute(sql)

        conn.commit()
        msg = "Created alias {} for player {}".format(new_name, old_name)
        logging.info(msg)
        await ctx.send(msg)

# store_in_backlog
# @param player_data, a tuple containing name, date, alliance, lv, and power
async def store_in_backlog(player_data):
    cur = conn.cursor()
    sql = '''INSERT INTO backlog (Name, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(player_data[0].lower(), player_data[1], player_data[2], player_data[3], player_data[4]);
    logging.debug('SQL: ' + sql)
    cur.execute(sql)


async def store_in_db_from_backlog(ctx, names):
    # Get a key for the new entry, or the key for the old name if the name is already in the database
        cur = conn.cursor()
        names_list = []
        alliance = ""
        lv_list = []
        power_list = []

        for name in names:
            sql = '''SELECT * FROM backlog WHERE Name="{}"'''.format(name.lower())
            logging.debug('SQL: ' + sql)
            cur.execute(sql)
            player_data_list = cur.fetchone()
            if player_data_list is not None:
                names_list.append(player_data_list[0])
                alliance = player_data_list[2]
                lv_list.append(player_data_list[3])
                power_list.append(player_data_list[4])

            sql = '''DELETE FROM backlog WHERE Name="{}"'''.format(name.lower())
            logging.debug('SQL: ' + sql)
            cur.execute(sql)

        await store_in_db(ctx, names_list, lv_list, power_list, alliance);


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
@bot.command(description="pong")
async def ping(ctx):
    logging.debug("Player " + str(ctx.message.author) + " running command \'ping\'")
    logging.info('pong')
    await ctx.send('pong')

# Add a player name to the dictionary. !add <player_name>
@bot.command(description="Add a player name to the dictionary. !add <player_name>")
async def add(ctx):
    logging.debug("Player " + str(ctx.message.author) + " running command \'add\'")
    args = ctx.message.content[5:].split(' ')
    file = open("STFC_dict.txt", "a")
    for arg in args:
        '''file.write(arg + "\n")
        #key = add_name_to_alias(arg)
        msg = 'Added \'' + arg + '\' to the dictionary'
        logging.info(msg)
        await ctx.send(msg)'''
        await add_name_to_dict(ctx, arg)

        # Get a key for the new entry, or the key for the old name if the name is already in the database
        cur = conn.cursor()
        sql = '''SELECT key FROM alias WHERE name="{}"'''.format(arg.lower());
        logging.debug('SQL: ' + sql)
        cur.execute(sql)
        value_list = cur.fetchone()
        key = -1
        if value_list is None:
            key = add_name_to_alias(arg)
        else:
            key = value_list[0]

        # store the data in the backlog into the LVE db
        #sql = '''SELECT (Name, Date, Alliance, Lv, Power) FROM backlog WHERE Name="{}"'''.format(arg)
        #logging.debug("SQL: " + sql)
        #cur.execute(sql)
        #value_list = cur.fetchone()
        #if value_list is not None:
        #    try:
        #        sql = '''INSERT INTO LVE (PlayerKey, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(key,
        #            value_list[1],
        #            value_list[2],
        #            int(value_list[3]),
        #            int(value_list[4]))
        #        cur.execute(sql)
        #        logging.debug("SQL: " + sql)
        #        #sql = '''DELETE FROM backlog WHERE PlayerKey={}'''.format(value_list[0])
        #        #cur.execute(sql)
        #        #logging.debug("SQL: " + sql)
        #        conn.commit()
        #
        #        msg = "Name: " + value_list[0] + ",\tLv: " + str(value_list[3]) + ",\tPower: " + str(value_list[4])
        #        logging.info(msg)
        #        await ctx.send(msg)
        #    except ValueError:
        #        err_msg = "[ERROR] Cannot interpret the power of player " + arg + " as an integer."
        #        logging.warning(err_msg, exc_info=True)
        #        await ctx.send(err_msg)

    await store_in_db_from_backlog(ctx, args);

    file.close()

# Add new roster screenshot data. !alliance <alliance_name> [attachment=image]
@bot.command(description="Add new roster screenshot data.")
async def alliance(ctx, alliance_name):
    logging.debug("Player " + str(ctx.message.author) + " running command \'alliance\'")
    await bot.change_presence(status=Status.dnd)
    num_attachments = len(ctx.message.attachments)
    if num_attachments < 1:
        msg = 'Please include a roster screenshot'
        logging.error(msg)
        await ctx.send(msg)
    else:

        # Delete any data currently stored in the backlog
        del_backlog = '''DELETE FROM backlog''';
        logging.debug("SQL: " + del_backlog)
        conn.cursor().execute(del_backlog)

        # Process each attachment
        for i in range(num_attachments):
            logging.debug("Looking at image " + str(i) + " of " + str(num_attachments))
            if not isImage(ctx, i):
                msg = 'Please only submit images. Stopping...'
                logging.error(msg)
                await ctx.send(msg)
                return False
            im_url = ctx.message.attachments[i].url
            await getImage(im_url)
            im = Image.open('latest.jpg')
            names_list = []
            level_list = []
            rgb = get_rgb_filter(im)
            if rgb is None:
                msg = "Unable to process screenshot"
                logging.error(msg)
                await ctx.send(msg)
                return False
            apply_img_mask(im, rgb, x_percent)
            if (await process_image(ctx, im, names_list, level_list)):
                await check_spelling(ctx, names_list)
                width, height = im.size
                power_list = []
                im_power = im.crop((math.floor(width/2), math.floor(height/10), width, height))
                power = pytesseract.image_to_string(im_power)
                power_list = power.split('\n')
                for i in range(len(power_list)):
                    power_list[i] = re.sub("[^0-9,]", "", power_list[i])
                power_list = list(filter(None, power_list))
                await store_in_db(ctx, names_list, level_list, power_list, alliance_name)
                await bot.change_presence(status=Status.online)


# Add a new alias. !alias <new_name> <old_name>
@bot.command(description="Add a new alias")
async def alias(ctx, new_name, old_name):
    await func_alias(ctx, new_name, old_name)

@bot.command(description="Get the time until the next reset for entering data")
async def time(ctx):
    logging.debug("Player " + str(ctx.message.author) + " running command \'time\'")
    midnight = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time())
    time_diff = (midnight - datetime.datetime.now()).seconds;
    hours, remainder = divmod(time_diff, 3600)
    minutes, seconds = divmod(remainder, 60)
    #msg = "The current time is " + datetime.datetime.now().strftime("%H:%M:%S") +"\n"
    msg=""
    if (time_diff > 3600):
        msg = "The next reset is in " + str(hours) + " hours and " + str(minutes+1) + " minutes"
    elif (time_diff > 60):
        msg = "The next reset is in " + str(minutes+1) + " minutes"
    else:
        msg = "The next reset in " + str(seconds) + " seconds" 
    logging.info(msg)
    await ctx.send(msg)

@bot.command(description="Correct a name in the backlog and submit the data for that player")
async def correct(ctx, incorrect_name_spelling, correct_name_spelling ):
    cur = conn.cursor()
    logging.debug("Player " + str(ctx.message.author) + " running command \'correct\'")
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(correct_name_spelling.lower())
    logging.debug('SQL: ' + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    key = -1
    if value_list is None:
        key = add_name_to_alias(correct_name_spelling)
    else:
        key = value_list[0]

    # add incorrect name to dictionary
    #await add_name_to_dict(ctx, incorrect_name_spelling)

    # make the correct name an alias of the incorrect name
    if (incorrect_name_spelling != correct_name_spelling):
        await func_alias(ctx, incorrect_name_spelling, correct_name_spelling)

    # store the data in the backlog into the LVE db
    await store_in_db_from_backlog(ctx, [incorrect_name_spelling]);

@bot.event
async def on_ready():
    logging.info("Logged in as " + bot.user.name)


# ------------------------------------------------------------------------------
#                                 MAIN SCRIPT
# ------------------------------------------------------------------------------
init_logger()
f = open(token_file, "r")
TOKEN = f.read()
bot.run(TOKEN)