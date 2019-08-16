# Work with Python 3.6
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

import traceback

# MODIFIABLE PARAMETERS
db_name = "LVE.db"
#db_name = "LVE"
x_percent = 14
bot = commands.Bot(command_prefix='!')

# CONNECTION SCRIPT
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

conn = create_connection(db_name)

@bot.command()
async def ping(ctx):
    await ctx.send('pong')

def add_name_to_alias(name):
    cur = conn.cursor()
    sql = '''SELECT value FROM __state WHERE name="key"'''
    print("SQL: " + sql)
    cur.execute(sql)
    key = cur.fetchone()[0]
    sql = '''INSERT INTO alias (key, name) VALUES ("{}", "{}")'''.format(key, name)
    print("SQL: " + sql)
    cur.execute(sql)
    new_key = int(key) + 1
    sql = '''UPDATE __state SET value={} WHERE name="key"'''.format(new_key)
    print("SQL: " + sql)
    cur.execute(sql)
    return key

def isImage(context, num):
    pic_ext = ['.jpg','.png','.jpeg']
    for ext in pic_ext:
        if context.message.attachments[num].filename.endswith(ext):
            return True
    return False

async def getImage(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            f = await aiofiles.open('latest.jpg', mode='wb')
            await f.write(await resp.read())
            await f.close()

def apply_img_mask(im, x_percent):
    pixdata = im.load()
    width, height = im.size
    x_cutoff = math.floor(width / x_percent)
    for x in range(width):
        for y in range(height):
            r,g,b = im.getpixel((x,y))
            if r < 220 or g < 220 or b < 220 or x < x_cutoff:
                #out.putpixel((x,y), 0)
                pixdata[x,y] = (255, 255, 255);
            else:
                pixdata[x,y] = (0,0,0,0)
            #else:
                #out.putpixel((x,y), (r,g,b))

async def process_image(ctx, im, names_list, level_list):
    width, height = im.size
    im_names = im.crop((0, 0, math.floor(width/2), height))
    names = pytesseract.image_to_string(im_names)
    tmp_list = names.split('\n\n')
    success = False
    __flag = False
    for tmp in tmp_list:
        if (bool(re.match(r"^[0-9]+ [a-zA-Z0-9]", tmp))):
            lv, name = tmp.split(' ', 1)
            level_list.append(lv)
            names_list.append(name)
            success = True
        elif (bool(re.match(r"^[0-9]+", tmp))):
            level_list.append(tmp)
            __flag = True
        elif (__flag):
            names_list.append(tmp)
            success = True
    if not success:
        msg = "Unable to process image, please try again."
        print(msg + " MSG: " + tmp)
        await ctx.send(msg)
    return True;

async def check_spelling(ctx, names_list):
    spell = SpellChecker(language=None, case_sensitive=False)
    spell.word_frequency.load_text_file("STFC_dict.txt")
    
    for i in range(len(names_list)):
        word = names_list[i].lower()

        if word in spell:
            names_list[i] = word
            print(word + " is spelled correctly!")
        else:
            cor = spell.correction(word)
            if (cor != word):
                print("Corrected '{}' to '{}'".format(word, cor))
                names_list[i] = cor;
            else:
                print("Unrecognized player name " + word + " in row " + str(i))
                print("If this is a new player, please add them to the dictionary by doing '!add <player name>'")
                names_list[i] = "DELETE_ME"
                await ctx.send("Unrecognized player name {} in row {}. If this is a new player, please add them to the dictionary by doing '!add <player name>'".format(word, i))
                continue

async def store_in_db(ctx, names_list, lv_list, power_list, team):
    for i in range(0, len(names_list)):
        if i <= len(lv_list) and i <= len(power_list) and names_list[i] != "DELETE_ME":
            cur = conn.cursor()
            sql = '''SELECT key FROM alias WHERE name="{}"'''.format(names_list[i]);
            print(sql)
            cur.execute(sql)
            value_list = cur.fetchone()
            key = -1
            if value_list is None:
                key = add_name_to_alias(names_list[i])
            else:
                key = value_list[0]

            sql = '''SELECT * FROM LVE WHERE PlayerKey={} AND Date="{}"'''.format(key, datetime.datetime.now().strftime("%Y-%m-%d"))
            print("SQL: " + sql)
            cur.execute(sql)
            value_list = cur.fetchone()
            if value_list is not None:
                err_msg = "Data for player {} has already been entered today. Skipping this player...".format(names_list[i])
                print(err_msg)
                await ctx.send(err_msg)
                continue
            try:
                sql = '''INSERT INTO LVE (PlayerKey, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(key,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                    team,
                    int(lv_list[i]),
                    int(power_list[i].replace(',', '')))
                print("SQL: " + sql)
                cur.execute(sql)
            except ValueError:
                err_msg = "Cannot interpret the power of player " + names_list[i] + " as an integer."
                print(err_msg + " ERR: " + traceback.format_exc())
                await ctx.send(err_msg)
                continue

            msg = "Name: " + names_list[i] + ",\tLv: " + lv_list[i] + ",\tPower: " + power_list[i]
            print(msg)
            await ctx.send(msg)
    conn.commit()
    #conn.close()

# Add a player name to the dictionary. !add <player_name>
@bot.command(description="Add a player name to the dictionary. !add <player_name>")
async def add(ctx):
    args = ctx.message.content[5:].split(' ')
    file = open("STFC_dict.txt", "a")
    for arg in args:
        file.write(arg + "\n")
        await ctx.send('Added \'' + arg + '\' to the dictionary')
    file.close()

# Add new roster screenshot data. !alliance <alliance_name> [attachment=image]
@bot.command(description="Add new roster screenshot data.")
async def alliance(ctx, alliance_name):
    await bot.change_presence(status=Status.dnd)
    #args = ctx.message.content[10:].split(' ')
    num_attachments = len(ctx.message.attachments)
    #if len(allaince_name) < 1:
    #    await ctx.send('Please specify an alliance')
    if num_attachments < 1:
        await ctx.send('Please include a roster screenshot')
    else:
        for i in range(num_attachments):
            print("Looking at image " + str(i) + " of " + str(num_attachments))
            if not isImage(ctx, i):
                await ctx.send('Please only submit images. Stopping...')
                return False
            im_url = ctx.message.attachments[i].url
            await getImage(im_url)
            im = Image.open('latest.jpg')
            names_list = []
            level_list = []
            apply_img_mask(im, x_percent)
            if (await process_image(ctx, im, names_list, level_list)):
                await check_spelling(ctx, names_list)
                width, height = im.size
                power_list = []
                im_power = im.crop((math.floor(width/2), 0, width, height))
                power = pytesseract.image_to_string(im_power)
                power_list = power.split('\n\n')
                await store_in_db(ctx, names_list, level_list, power_list, alliance_name)
                await bot.change_presence(status=Status.online)


# Add a new alias. !alias <new_name> <old_name>
@bot.command()
async def alias(ctx):
    args = ctx.message.content[7:].split(' ')
    cur = conn.cursor()
    if (len(args) < 2):
        await ctx.send("Not enough arguments. Please add an alias using the format !alias <new_name> <old_name>")
        return False
    new_name = args[0].lower()
    old_name = args[1].lower()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(old_name)
    print("SQL: " + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    if value_list is None:
        #add_name_to_alias(args[0])
        await ctx.send("The player \"" + args[1] + "\" does not exist. Please add an alias using the format !alias <new_name> <old_name>")
    else:
        key = value_list[0]
        # check if the new name already exists in the database
        sql = '''SELECT key FROM alias WHERE name="{}"'''.format(new_name)
        print("SQL: " + sql)
        cur.execute(sql)
        value_list_2 = cur.fetchone()
        if value_list_2 is None:
            sql = '''INSERT INTO alias (key, name) VALUES ("{}", "{}")'''.format(key, new_name)
            print("SQL: " + sql)
            cur.execute(sql)
        else:
            sql = '''UPDATE alias SET key={} WHERE name="{}"'''.format(key, new_name)
            print("SQL: " + sql)
            cur.execute(sql)

        conn.commit()
        await ctx.send("Created alias {} for player {}".format(args[0], args[1]))



@bot.event
async def on_ready():
    print("Logged in as " + bot.user.name)

# MAIN SCRIPT
#BOT_PREFIX = ("?", "!")
f = open("secret.txt", "r")
TOKEN = f.read()
bot.run(TOKEN)