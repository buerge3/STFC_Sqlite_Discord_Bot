#!/usr/bin/env python
#
# FILENAME: vision-test.py
# CREATED:  August 17, 2019
# AUTHOR:   buerge3
#
# A command-line script for testing image-processing functionality indpendentent
# of sqlite or discord. Expects a screenshot of an STFC roster as the first
# command-line argument.
# Usage: "python ./vision-test.py <image_file_path>"

import sqlite3                                   # sqlite3        - connects to the database
from sqlite3 import Error
from PIL import Image                            # PIL            - loads and preprocesses images
import pytesseract                               # Tesseract OCR  - converts images to strings
import math                                      # math           - performs basic math operations such as min/max
from spellchecker import SpellChecker            # pyspellchecker - corrects player names using the dictionary
import re                                        # re             - handles regular expressions
import sys                                       # sys            - parses command line arguments
import datetime                                  # datetime       - gets the current date and time

# MODIFIABLE PARAMTERS
db_name = "test.db"
x_percent = 0.12

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
        print("connected to " + db_file);
        return conn
    except Error as e:
        print(e)

    return None

conn = create_connection(db_name)

# -----------------------------------------------------------------------------
#                                    FUNCTIONS
# -----------------------------------------------------------------------------
# add_player
# adds a player to the dictionary/alias table if they do not exist, otherwise just
# sets the alias table entry to active
# @param name, a player name string
# @return key of the added player
def add_player(name):
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="name"'''
    print("SQL: " + sql)
    cur.execute(sql)
    res = cur.fetchone()
    if res:
        sql = '''UPDATE alias SET active=1 WHERE key={}'''.format(res[0])
        return res[0]
    # the player does not exist, add them
    sql = '''SELECT value FROM __state WHERE name="key"'''
    print("SQL: " + sql)
    cur.execute(sql)
    key = cur.fetchone()[0]
    sql = '''INSERT INTO alias (key, name, date) VALUES ("{}", "{}")'''.format(key, name.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
    print("SQL: " + sql)
    cur.execute(sql)
    new_key = int(key) + 1
    sql = '''UPDATE __state SET value={} WHERE name="key"'''.format(new_key)
    print("SQL: " + sql)
    cur.execute(sql)
    return key

# isImage
# @param img_path, the path to an image
# @return true if the specified path is an image
def isImage(img_path):
    return img_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'))

# get_rgb_filter
# @param im, the STFC roster screenshot to find appropriate filter values for
# @returns rgb, a three-element list consisting of the rgb values for the filter
def get_rgb_filter(im):
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
            print(msg)
            return None

        print("I read: " + word)
        if (bool(re.search(r"MEMBERS", word))):
            print("found a working filter! I see: " + word)
            return rgb;
        else:
            rgb[0] -= 20
            rgb[1] -= 20
            rgb[2] -= 20
    msg = "**[ERROR]** Unable to find a suitable rgb filter";
    print(msg)
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
def process_name(im, names_list, level_list):
    #width, height = im.size
    #im_names = im.crop((0, math.floor(height/10), math.floor(width/2), height))
    try:
        text = pytesseract.image_to_string(im, config='--psm 7')
    except Error as err:
        msg = "**[ERROR]** {0}".format(err)
        print(msg)
        return False
    booboo = re.search(r"[1-5][\]\)l] ", text)
    if (bool(booboo)):
        text = text[booboo.start()] + "1 " + text[booboo.end():]
    match = re.search(r"[0-9]+ {1,3}\S", text)
    if (bool(match)):
        #text = re.sub(r'^\W+', '', text)
        text = text[match.start():]
        lv, name = re.split(' {1,3}', text, 1)
        name = name.replace(" ", "_")
        name = re.sub(r'^[0-9]+_', '', name)
        heart_match = re.search(r"[a-zA-Z0-9]", name); # check for extra whitespace created by hearts
        if (bool(heart_match)):
            name = name[heart_match.start():] # handle extra whitespace created by hearts
        level_list.append(lv)
        names_list.append(name)
        return True
    else:
        #msg = "**[ERROR]** Unable to process image; cause: did not discover any data in the expected format"
        msg = "**[ERROR]** Unable to process line {}; cause: did not discover data in the expected format".format(text)
        print(msg)
        im.show()
        return False

# load_dictionary
# @param spell_check, an instance of spell checker
def load_dictionary(spell_check):
    cur = conn.cursor()
    sql = '''SELECT name FROM alias WHERE active=1'''
    cur.execute(sql)
    word_list = []
    for row in cur.fetchall():
        word_list.append(row[0])
    spell_check.word_frequency.load_words(word_list)

# check_spelling
# @param spell, the spell checker to use for spell checking
# @param names_list, a list of player names to check the spelling of
#         using the dictionary file 'STFC_dict.txt'
# @param mispelled, an empty list to populate with mispelled names
def check_spelling(spell, names_list, mispelled):
    
    for i in range(len(names_list)):
        if (names_list[i] == "DELETE_ME"):
            continue
        word = names_list[i]

        if word in spell:
            names_list[i] = word
            print(word + " is spelled correctly!")
        else:
            cor = spell.correction(word)
            if (cor != word):
                print("Corrected '{}' to '{}'".format(word, cor))
                names_list[i] = cor;
            else:
                mispelled.append(word)
                msg = "**[WARNING]** Unrecognized player name {}".format(word)
                print(msg)
                names_list[i] = "DELETE_ME" + names_list[i]
                continue

# store_in_db
# @param names_list, a list of player names
# @param lv_list, a list of player levels
# @param power_list, a list of player power
# @param which alliance the roster screenshot belongs to
# this method only displays what values would be entered into the database,
# and does not store this data in an actual database
def store_in_db(names_list, lv_list, power_list, team):
    for i in range(len(names_list)):
        if i < len(lv_list) and i < len(power_list) and names_list[i] != "DELETE_ME":
            msg = "Name: " + names_list[i] + ",\tLv: " + lv_list[i] + ",\tPower: " + power_list[i]
            print(msg)


# ------------------------------------------------------------------------------
#                                 MAIN SCRIPT
# ------------------------------------------------------------------------------
if len(sys.argv) < 2:
    print('Usage: python3 ./vision-test [image-name]')
elif not conn:
    print('Failed to connect to database. Stopping...')
else:
    spell_checker = SpellChecker(language=None, case_sensitive=False)
    load_dictionary(spell_checker)

    mispelled_list = []
    success_count = 0
    failed_count = 0

    for img_path in sys.argv[1:]:
        if not isImage(img_path):
            print('Please only submit images. Stopping...')
            break
        im = Image.open(img_path).convert("RGB")
        pixdata = im.load()
        width, height = im.size
        x_cutoff = math.floor(width / x_percent)
        names_list = []
        level_list = []
        exclude = [0] * 7
        rgb = get_rgb_filter(im)
        if rgb is None:
            msg = "**[ERROR]** Unable to process screenshot; cause: failed to determine a suitable rgb filter"
            print(msg)
        else:
            apply_img_mask(im, rgb, x_percent)

            for k in range(7):
                a = 2 * height / 10
                b = (( height - a) / 7 ) * k
                c = (( height - a) / 7 ) * (k + 1)
                im_names = im.crop((  0, math.floor( a + b ) , math.floor(width/2), math.floor( a + c ) ))
                #tasks.append(process_image(ctx, im_names, names_list, level_list))
                if not process_name(im_names, names_list, level_list):
                    exclude[k] = 1
            #im.show()
            check_spelling(spell_checker, names_list, mispelled_list)

            power_list = []
            im_power = im.crop((math.floor(width/2), math.floor(height/10), width, height))

            try:
                power = pytesseract.image_to_string(im_power)
            except TesseractError as err:
                fail_count += 7;
                msg = "**[ERROR]** {0}".format(err)
                print(msg)
                quit()

            power_list = power.split('\n')
            for i in range(len(power_list)):
                power_list[i] = re.sub("[^0-9,]", "", power_list[i])
            power_list = list(filter(None, power_list))
            new_power_list = []
            for i in range(7):
                if not exclude[i]:
                    new_power_list.append(power_list[i])
            store_in_db(names_list, level_list, new_power_list, "TEST")
