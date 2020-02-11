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

import asyncio
import aiohttp
import aiofiles

import datetime
import re

import logging

# MODIFIABLE PARAMETERS
db_name = "LVE.db"
token_file = "secret_vision.txt"
x_percent = 0.17
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
async def get_rgb_filter(ctx, im):
    width, height = im.size
    rgb = [220, 220, 220]
    for i in range(4):
        im_rgb = im.crop((0, 0, width, math.floor(height/10)))
        #logging.debug("trying r=" + str(rgb[0]), ", g=" + str(rgb[1]) + ", b=" + str(rgb[2]))
        apply_img_mask(im_rgb, rgb, 0)
        try:
            word = pytesseract.image_to_string(im_rgb)
        except TesseractError as err:
            msg = "**[ERROR]** {0}".format(err)
            logging.error(msg)
            await ctx.send(msg)
            return None

        logging.debug("I read: " + word)
        if (bool(re.search(r"MEMBERS", word))):
            logging.debug("found a working filter! I see: " + word)
            return rgb;
        else:
            rgb[0] -= 20
            rgb[1] -= 20
            rgb[2] -= 20
    msg = "**[ERROR]** Unable to find a suitable rgb filter";
    logging.error(msg)
    await ctx.send(msg)
    return None

# apply_img_mask
# @param im, the image to apply a mask to
# @param rgb, a three-element list consisting of the rgb values for the mask threshold
# @param x_percent, what percentage of the width to crop off from the right. Used to
#        remove STFC rank symbols for premier, commodore, etc
def apply_img_mask(im, rgb, x_percent):
    pixdata = im.load()
    width, height = im.size
    x_cutoff = math.floor(width * x_percent)
    for x in range(width):
        for y in range(height):
            r,g,b = im.getpixel((x,y))
            if r < rgb[0] or g < rgb[1] or b < rgb[2] or x < x_cutoff:
                #out.putpixel((x,y), 0)
                pixdata[x,y] = (255, 255, 255);
            else:
                pixdata[x,y] = (0,0,0,0)

# process_name
# @param im, an STFC roster screenshot
# @param names_list, an empty list to populate with player names
# @param level_list, an empty list to populate with player levels
# @return True if success, False if an error occurred
async def process_name(ctx, im, names_list, level_list):
    #width, height = im.size
    #im_names = im.crop((0, math.floor(height/10), math.floor(width/2), height))
    try:
        text = pytesseract.image_to_string(im, config='--psm 7')
    except Error as err:
        msg = "**[ERROR]** {0}".format(err)
        logging.error(msg)
        await ctx.send(msg)
        return False
    match = re.search(r"[0-9]+ \S", text)
    if (bool(match)):
        #text = re.sub(r'^\W+', '', text)
        text = text[match.start():]
        lv, name = text.split(' ', 1)
        name = name.replace(" ", "_")
        name = re.sub(r'^[0-9]+_', '', name)
        level_list.append(lv)
        names_list.append(name)
        return True
    else:
        #msg = "**[ERROR]** Unable to process image; cause: did not discover any data in the expected format"
        msg = "**[ERROR]** Unable to process line {}; cause: did not discover data in the expected format".format(text)
        logging.error(msg)
        await ctx.send(msg)
        return False

# check_spelling
# @param names_list, a list of player names to check the spelling of
#         using the dictionary file 'STFC_dict.txt'
async def check_spelling(ctx, names_list, mispelled):
    spell = SpellChecker(language=None, case_sensitive=False)
    spell.word_frequency.load_text_file("STFC_dict.txt")
    
    for i in range(len(names_list)):
        if (names_list[i] == "DELETE_ME"):
            continue
        word = names_list[i]

        if word in spell:
            names_list[i] = word
            logging.debug(word + " is spelled correctly!")
        else:
            cor = spell.correction(word)
            if (cor != word):
                logging.debug("Corrected '{}' to '{}'".format(word, cor))
                names_list[i] = cor;
            else:
                mispelled.append(word)
                msg = "**[WARNING]** Unrecognized player name {}".format(word)
                logging.warning(msg)
                await ctx.send(msg)
                names_list[i] = "DELETE_ME" + names_list[i]
                continue

def get_key (name):
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(name)
    logging.debug('SQL: ' + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    key = -1
    if value_list is None:
        key = add_name_to_alias(name)
    else:
        key = value_list[0]
    return key

# store_in_db
# @param names_list, a list of player names
# @param lv_list, a list of player levels
# @param power_list, a list of player power
# @param which alliance the roster screenshot belongs to
async def store_in_db(ctx, names_list, lv_list, power_list, team):

    cur = conn.cursor()

    success_count = 0;
    warn_count = 0;
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
            key = get_key(names_list[i].lower())

            sql = '''SELECT * FROM LVE WHERE PlayerKey={} AND Date="{}"'''.format(key, datetime.datetime.now().strftime("%Y-%m-%d"))
            logging.debug("SQL: " + sql)
            cur.execute(sql)
            value_list = cur.fetchone()
            if value_list is not None:
                warn_count += 1
                err_msg = "**[WARNING]** Data for player {} has already been entered today. Skipping this player...".format(names_list[i])
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
                
            except ValueError as err:
                #err_msg = "**[ERROR]** Cannot interpret the power of player {} as an integer; Power: {}".format(names_list[i], str(power_list[i]).replace(',', ''))
                err_msg = "**[ERROR]** {}".format(err)
                logging.warning(err_msg, exc_info=True)
                await ctx.send(err_msg)
                continue

            if target == "LVE":
                success_count += 1
                msg = "Name: " + names_list[i] + ", Lv: " + str(lv_list[i]) + ", Power: " + str(power_list[i])
                logging.info(msg)
                await ctx.send(msg)
    conn.commit()
    return success_count, warn_count

# func_alias
# @param ctx, Discord msg context
# @param new_name, player name string
# @param old_name, player name string
async def func_alias(ctx, new_name, old_name):
    logging.debug("Player " + str(ctx.message.author) + " running command \'alias\'")

    # add alias
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(old_name.lower())
    logging.debug("SQL: " + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    if value_list is None:
        #add_name_to_alias(args[0])
        msg = "**[ERROR]** The player \"" + old_name + "\" does not exist. Please add an alias using the format !alias <new_name> <old_name>"
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

# store_in_db_from_backlog
# @param names, a list of names to restore from the backlog
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

# process_screenshot
# @param i, index of the screenshot to process
# @return success_count, # of names successfully uploded to the LVE database
async def process_screenshot(ctx, i, alliance_name, mispelled_list):

    if not isImage(ctx, i):
        msg = '**[ERROR]** Attachment #{} is not an image. Please only submit images.'.format(i + 1)
        logging.error(msg)
        await ctx.send(msg)
        return 0
    im_url = ctx.message.attachments[i].url
    await getImage(im_url)
    im = Image.open('latest.jpg')
    names_list = []
    level_list = []
    exclude = [0] * 7
    rgb = await get_rgb_filter(ctx, im)
    if rgb is None:
        msg = "**[ERROR]** Unable to process screenshot #{}; cause: failed to determine a suitable rgb filter".format(i + 1)
        logging.error(msg)
        await ctx.send(msg)
        return 0
    else:
        msg = "Processing screenshot #{}:".format(i + 1)
        logging.info(msg)
        await ctx.send(msg)

    width, height = im.size
    apply_img_mask(im, rgb, x_percent)
    for k in range(7):
        a = 2 * height / 10
        b = (( height - a) / 7 ) * k
        c = (( height - a) / 7 ) * (k + 1)
        im_names = im.crop((  0, math.floor( a + b ) , math.floor(width/2), math.floor( a + c ) ))
        #tasks.append(process_image(ctx, im_names, names_list, level_list))
        if not await process_name(ctx, im_names, names_list, level_list):
            exclude[k] = 1

    await check_spelling(ctx, names_list, mispelled_list)
    power_list = []
    im_power = im.crop((math.floor(width/2), math.floor(height/10), width, height))

    try:
        power = pytesseract.image_to_string(im_power)
    except TesseractError as err:
        fail_count += 7;
        msg = "**[ERROR]** {0}".format(err)
        logging.error(msg)
        await ctx.send(msg)
        return 0

    power_list = power.split('\n')
    for i in range(len(power_list)):
        power_list[i] = re.sub("[^0-9,]", "", power_list[i])
    power_list = list(filter(None, power_list))
    new_power_list = []
    for i in range(7):
        if not exclude[i]:
            new_power_list.append(power_list[i])
    success_count, warn_count = await store_in_db(ctx, names_list, level_list, new_power_list, alliance_name.lower())
    return success_count, warn_count

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
        key = get_key(arg.lower())

    await store_in_db_from_backlog(ctx, args);

    file.close()

# Add new roster screenshot data. !alliance <alliance_name> [attachment=image]
@bot.command(description="Add new roster screenshot data.", aliases=["upload", "upload-alliance"])
async def alliance(ctx, alliance_name):
    logging.debug("Player " + str(ctx.message.author) + " running command \'alliance\'")
    num_attachments = len(ctx.message.attachments)
    if num_attachments < 1:
        msg = '**[ERROR]** Please include a roster screenshot'
        logging.error(msg)
        await ctx.send(msg)
        return
    else:

        # Delete any data currently stored in the backlog
        del_backlog = '''DELETE FROM backlog''';
        logging.debug("SQL: " + del_backlog)
        conn.cursor().execute(del_backlog)

        mispelled_list = []
        success_count = 0
        already_uploaded_count = 0;
        failed_count = 0
        for i in range(num_attachments):
            try:
                async with ctx.message.channel.typing():
                    num_success, num_warn = await process_screenshot(ctx, i, alliance_name, mispelled_list)
            except UnicodeDecodeError:
                msg = "**[ERROR]** The dictionary contains at least one non-unicode character"
                logging.error(msg)
                await ctx.send(msg)
                return
            success_count += num_success
            already_uploaded_count += num_warn
            failed_count += 7 - num_success - num_warn
        failed_count -= len(mispelled_list)
        if len(mispelled_list) == 0:
            mispelled_msg = "No mispelled names"
        else:
            mispelled_msg = ", ".join(mispelled_list)
        if failed_count == 0:
            failed_msg = "No errors"
        else:
            failed_msg = "Unable to process {} names due to errors".format(failed_count)
        embed=discord.Embed(title="Upload Report for {}".format(ctx.message.author), color=0xff0000)
        embed.add_field(name="SUCCESS ({}):".format(success_count), value="Uploaded data for {} unique players".format(success_count), inline=False)
        embed.add_field(name="UNRECOGNIZED NAMES ({}):".format(len(mispelled_list)), value=mispelled_msg, inline=False)
        embed.add_field(name="ALREADY UPLOADED ({}):".format(already_uploaded_count), value="No data was uploaded for {} names since their data for today is already stored".format(already_uploaded_count), inline=False)
        embed.add_field(name="FAILED ({}):".format(failed_count), value=failed_msg, inline=False)
        await ctx.send("Done.", embed=embed)


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

@bot.command(description="Create a new alias for a player", aliases=["alias", "link"])
async def correct(ctx, incorrect_name_spelling, correct_name_spelling ):
    logging.debug("Player " + str(ctx.message.author) + " running command \'correct\'")

    # make the correct name an alias of the incorrect name
    if (incorrect_name_spelling != correct_name_spelling):
        await add_name_to_dict(ctx, incorrect_name_spelling) # add incorrect name to dictionary
        await func_alias(ctx, incorrect_name_spelling, correct_name_spelling) # create the alias
    else:
        msg = "**[WARNING]** The old name and new names are the same, so the command was not run. Try using 'add' instead!"
        logging.warning(msg)
        await ctx.send(msg)

    # store the data in the backlog into the LVE db
    await store_in_db_from_backlog(ctx, [incorrect_name_spelling]);


@bot.command(description="Display the daily upload status for a team", aliases=["upload-status"])
async def status(ctx, team ):
    cur = conn.cursor()
    logging.debug("Player " + str(ctx.message.author) + " running command \'status\'")
    sql = '''SELECT COUNT(*) FROM LVE  WHERE Alliance="{}" AND Date="{}"'''.format(team.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
    logging.debug('SQL: ' + sql)
    cur.execute(sql)
    num_data = cur.fetchone()
    if num_data is not None and num_data[0] > 0:
        sql = '''SELECT Name FROM backlog WHERE Alliance="{}" AND Date="{}"'''.format(team.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
        logging.debug('SQL: ' + sql)
        cur.execute(sql)
        player_data_list = cur.fetchall()
        msg = "Successfully uploaded {} names. There are {} mispelled names in the backlog.".format(num_data[0], len(player_data_list))
        if len(player_data_list) > 0:
            msg += "\nBACKLOG:\n"
            for row in player_data_list:
                msg += "\t" + row[0] + "\n"
        logging.info(msg)
        await ctx.send(msg)
    else:
        msg = "No data has been uploaded for team {} today".format(team)
        logging.info(msg)
        await ctx.send(msg)

@bot.event
async def on_ready():
    logging.info("Logged in as " + bot.user.name)


'''@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("[ERROR] Bad argument")
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("[ERROR] Missing required argument")
    else:
        await ctx.send("[ERROR] {}".format(error))'''

# ------------------------------------------------------------------------------
#                                 MAIN SCRIPT
# ------------------------------------------------------------------------------
init_logger()
f = open(token_file, "r")
TOKEN = f.read()
bot.run(TOKEN)