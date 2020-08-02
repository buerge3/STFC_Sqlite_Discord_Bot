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
import datetime                                  # datetime       - gets the current date and time
import argparse                                  # argparse       - process command line arguments

# MODIFIABLE PARAMTERS
db_name = "test.db"
x_percent = 0.12

# -----------------------------------------------------------------------------
#                        DATABASE CONNECTION SCRIPT
# -----------------------------------------------------------------------------
# create_connection
# create a database connection to the SQLite database specified by the db_file
# @param db_file, a database file
# @return, connection object or none
def create_connection(db_file):
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
# isImage
# determine if the supplied path corresponds to a valid image
# @param img_path, the path to an image
# @return true if the specified path is an image
def isImage(img_path):
    return img_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'))

# get_rgb_filter
# guess image filters until you find one that works... you know that a filter
# works when you can read the word "MEMBERS" on the alliance roster screenshot
# @param im, the STFC roster screenshot to find appropriate filter values for
# @returns rgb, a three-element list consisting of the rgb values for the filter
def get_rgb_filter(im):
    width, height = im.size
    rgb = [220, 220, 220]
    for i in range(4):
        im_rgb = im.crop((0, 0, width, math.floor(height/10)))
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
# modify the supplied image s.t. all pixel values below the threshold become white, and all
# pixels above the threshold become black
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
# extract player names and levels from a excerpt of an alliance roster
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
        #im.show()
        return False

# load_dictionary
# populate the spell checker frequency list from the database
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
# correct the player names in a list, and stash the names that cannot be corrected
# into a separate list
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
# get_key
# retrieve the unique database identifier for a player
# @param name, a player name
# @return key, unique database identifier for a player
def get_key (name):
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(name)
    print('SQL: ' + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    key = -1
    if value_list is None:
        key = add_name_to_alias(name)
    else:
        key = value_list[0]
    return key

# create_alias
# @param new_name, player name string
# @param old_name, player name string
def create_alias(new_name, old_name):

    # add alias
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(old_name.lower())
    print("SQL: " + sql)
    cur.execute(sql)
    value_list = cur.fetchone()
    if value_list is None:
        #add_name_to_alias(args[0])
        msg = "**[ERROR]** The player \"" + old_name + "\" does not exist. Please add an alias using the format !alias <new_name> <old_name>"
        print(msg)
    else:
        old_name_key = value_list[0]
        # check if the new name already exists in the database
        sql = '''SELECT key FROM alias WHERE name="{}"'''.format(new_name.lower())
        print("SQL: " + sql)
        cur.execute(sql)
        value_list_2 = cur.fetchone()
        if value_list_2 is None:
            sql = '''INSERT INTO alias (key, name, date) VALUES ("{}", "{}", "{}")'''.format(old_name_key, new_name.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
            print("SQL: " + sql)
        else:
            new_name_key = value_list_2[0]
            sql = '''UPDATE alias SET key_old={} WHERE key="{}"'''.format(new_name_key, new_name_key)
            print("SQL: " + sql)
            sql = '''UPDATE alias SET key={} WHERE key="{}"'''.format(old_name_key, new_name_key)
            print("SQL: " + sql)
            cur.execute(sql)
            sql = '''UPDATE main SET key={} WHERE key="{}"'''.format(old_name_key, new_name_key)
            print("SQL: " + sql)
            cur.execute(sql)

        conn.commit()
        msg = "Created alias {} for player {}".format(new_name, old_name)
        print(msg)

# store_in_db
# insert alliance roster data into the database, and optionally weed out bad power values
# @param names_list, a list of player names
# @param lv_list, a list of player levels
# @param power_list, a list of player power
# @param team, which alliance the roster screenshot belongs to
# @param check_power, true = verify the power value for each player is within 10% of previous
# this method only displays what values would be entered into the database,
# and does not store this data in an actual database
def store_in_db(names_list, lv_list, power_list, team, check_power):

    cur = conn.cursor()

    success_count = 0;
    warn_count = 0;
    power_err_count = 0;
    reason = 0; # reason for storing in the backlog: 0=misspelled, 1=suspicious power, 2=new player

    for i in range(0, len(names_list)):

        ## should name go into the main database or the backlog?
        target = ""
        if "DELETE_ME" in names_list[i]:
            target="backlog"
            names_list[i] = names_list[i][9:] # remove "DELETE_ME" from the name string
        else:
            target="main"

        if (names_list[i] == ""):
            continue

        if target=="main" and i < len(lv_list) and i < len(power_list):
            key = get_key(names_list[i].lower())

            ## if data for this player has already been entered today, skip this player
            sql = '''SELECT * FROM main WHERE key={} AND Date="{}"'''.format(key, datetime.datetime.now().strftime("%Y-%m-%d"))
            cur.execute(sql)
            value_list = cur.fetchone()
            if value_list is not None:
                warn_count += 1
                err_msg = "**[WARNING]** Data for player {} has already been entered today. Skipping this player...".format(names_list[i])
                print(err_msg)
                continue

            ## verify that both level and power are valid integers
            try:
                int(lv_list[i])
            except ValueError as Err:
                err_msg = "**[ERROR]** The level of player {} is \"{}\", which is not a number.".format(names_list[i], lv_list[i]);
                print(err_msg, exc_info=True)
                continue
            try:
                int(str(power_list[i]).replace(',', ''))
            except ValueError as Err:
                err_msg = "**[ERROR]** The power of player {} is \"{}\", which is not a number.".format(names_list[i], power_list[i]);
                continue

            ## confirm the power value is within the valid range!
            if check_power and target=="main":
                sql = '''SELECT Power FROM main WHERE key="{}" ORDER BY Date DESC LIMIT 1;'''.format(key, datetime.datetime.now().strftime("%Y-%m-%d"))
                print("SQL: " + sql)
                cur.execute(sql)
                recent = cur.fetchone()
                if recent is None or len(recent) == 0:
                    target = "backlog"
                    reason = 2
                    err_msg = "**[WARNING]** The player {} is new, please confirm that their power is {} by typing !confirm {}".format(names_list[i], power_list[i], names_list[i])
                    print(err_msg)
                    power_err_count += 1
                else:
                    try:
                        power = int(str(power_list[i]).replace(',', ''))
                        delta_power = (power - recent[0]) / power
                        if (abs(delta_power) > 0.1):
                            # second chance: try removing just the first digit
                            tmp_power = str(power_list[i]).replace(',', '')
                            power_list[i] = tmp_power[1:]
                            power = int(tmp_power[1:])
                            delta_power = (power - recent[0]) / power
                        if (abs(delta_power) > 0.1):
                            target = "backlog"
                            reason = 1
                            err_msg = "**[WARNING]** The player {} has power {}, which seems wrong. If it is correct, please type !confirm {}".format(names_list[i], power_list[i], names_list[i])
                            print(err_msg)
                            power_err_count += 1

                    except ValueError as err:
                        #err_msg = "**[ERROR]** Cannot interpret the power of player {} as an integer; Power: {}".format(names_list[i], str(power_list[i]).replace(',', ''))
                        err_msg = "**[ERROR]** {}".format(err)
                        print(err_msg)
                        continue

            ## store in the database
            if (target == "main"):
                sql = '''INSERT INTO main (key, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(key,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                    team,
                    int(lv_list[i]),
                    int(str(power_list[i]).replace(',', '')))
                print("SQL: " + str(sql))
                cur.execute(sql)
            else:
                #sql = '''INSERT INTO {} (Name, Date, Alliance, Lv, Power) VALUES ("{}", "{}", "{}", "{}", "{}")'''.format(target, names_list[i],
                #    datetime.datetime.now().strftime("%Y-%m-%d"),
                #    team,
                #    int(lv_list[i]),
                #    int(power_list[i].replace(',', '')))
                store_in_backlog((names_list[i], datetime.datetime.now().strftime("%Y-%m-%d"), team, lv_list[i], power_list[i], True), reason)

            if target == "main":
                success_count += 1
                msg = "Name: " + names_list[i] + ", Lv: " + str(lv_list[i]) + ", Power: " + str(power_list[i])
                print(msg)

    conn.commit()
    return success_count, warn_count, power_err_count

# store_in_backlog
# @param player_data, a tuple containing name, date, alliance, lv, and power
def store_in_backlog(player_data, reason=0):
    if reason < 0 or reason > 2:
        print("Invalid reason. Valid reasons are 0=misspelled, 1=suspicious power, 2=new player")
        return
    cur = conn.cursor()
    sql = '''INSERT INTO backlog (Name, Date, Alliance, Lv, Power, Reason) VALUES ("{}", "{}", "{}", "{}", "{}", "{}")'''.format(player_data[0].lower(), player_data[1], player_data[2], player_data[3], player_data[4], reason);
    print('SQL: ' + sql)
    cur.execute(sql)

# store_in_db_from_backlog
# @param names, a list of names to restore from the backlog
def store_in_db_from_backlog(names, check_power):
    # Get a key for the new entry, or the key for the old name if the name is already in the database
        cur = conn.cursor()
        names_list = []
        alliance = ""
        lv_list = []
        power_list = []

        for name in names:
            sql = '''SELECT * FROM backlog WHERE Name="{}"'''.format(name.lower())
            print('SQL: ' + sql)
            cur.execute(sql)
            player_data_list = cur.fetchone()
            if player_data_list is not None:
                names_list.append(player_data_list[0])
                alliance = player_data_list[2]
                lv_list.append(player_data_list[3])
                power_list.append(player_data_list[4])

            sql = '''DELETE FROM backlog WHERE Name="{}"'''.format(name.lower())
            print('SQL: ' + sql)
            cur.execute(sql)

        store_in_db(names_list, lv_list, power_list, alliance, check_power);

# -----------------------------------------------------------------------------
#                                TEST COMMANDS
# -----------------------------------------------------------------------------
# upload
# @param team, alliance name string
# @param ss, list of STFC screenshot paths
def upload(team, ss):
    spell_checker = SpellChecker(language=None, case_sensitive=False)
    load_dictionary(spell_checker)

    mispelled_list = []
    success_count = 0
    failed_count = 0

    mispelled_list = []
    success_count = 0
    already_uploaded_count = 0;
    failed_count = 0
    power_warn_count = 0;
    for img_path in ss:
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
                return

            power_list = power.split('\n')
            for i in range(len(power_list)):
                power_list[i] = re.sub("[^0-9,]", "", power_list[i])
            power_list = list(filter(None, power_list))
            new_power_list = []
            for i in range(7):
                if not exclude[i]:
                    new_power_list.append(power_list[i])
            num_success , num_warn, num_power_warn = store_in_db(names_list, level_list, new_power_list, team, True)
            success_count += num_success
            already_uploaded_count += num_warn
            power_warn_count += num_power_warn
            failed_count += 7 - num_success - num_warn - num_power_warn
    failed_count -= len(mispelled_list)
    if len(mispelled_list) == 0:
        mispelled_msg = "No mispelled names"
    else:
        mispelled_msg = ", ".join(mispelled_list)
    if power_warn_count == 0:
        power_msg = "No power warnings"
    else:
        power_msg = "The power of {} players looks suspicious, if these values are correct then do !confirm".format(power_warn_count)
    if failed_count == 0:
        failed_msg = "No errors"
    else:
        failed_msg = "Unable to process {} names due to errors".format(failed_count)

# add_player
# adds a player to the dictionary/alias table if they do not exist, otherwise just
# sets the alias table entry to active
# @param name, a player name string
# @return key of the added player
def add_player(name):
    cur = conn.cursor()
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(name.lower())
    print("SQL: " + sql)
    cur.execute(sql)
    res = cur.fetchone()
    if res:
        sql = '''UPDATE alias SET active=1 WHERE key={}'''.format(res[0])
        cur.execute(sql)
        conn.commit()
        msg = 'Re-added \'' + name + '\' to the dictionary'
        print(msg)
        return res[0]
    # the player does not exist, add them
    sql = '''SELECT value FROM __state WHERE name="key"'''
    print("SQL: " + sql)
    cur.execute(sql)
    key = cur.fetchone()[0]
    sql = '''INSERT INTO alias (key, name, date) VALUES ("{}", "{}", "{}")'''.format(key, name.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
    print("SQL: " + sql)
    cur.execute(sql)
    new_key = int(key) + 1
    sql = '''UPDATE __state SET value={} WHERE name="key"'''.format(new_key)
    print("SQL: " + sql)
    cur.execute(sql)
    conn.commit()
    msg = 'Added \'' + name + '\' to the dictionary'
    print(msg)
    return key

# remove_player
# deactivate the specified player name and all aliases
# @param name, a player name string
# @return key of the removed player, or -1 if the player does not exist
def remove_player(name):
    cur = conn.cursor()
    key = -1
    sql = '''SELECT key FROM alias WHERE name="{}"'''.format(name.lower())
    print("SQL: " + sql)
    cur.execute(sql)
    res = cur.fetchone()
    if not res:
        msg = 'Player \'' + new_name + '\' is not in the dictionary'
        print(msg)
        return -1
    sql = '''UPDATE alias SET active=0 WHERE key={}'''.format(res[0])
    conn.commit()
    msg = 'Removed \'' + new_name + '\' from the dictionary'
    print(msg)
    return res[0]

# time
# displays the time until midnight
def time():
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
    print(msg)

# correct
# adds a new player name to the dictionary and make it an alias of an existing player
# @param incorrect_name_spelling, a new name to add to the dictionary
# @param correct_name_spelling, the new name will be an alias of this name
def correct(incorrect_name_spelling : str, correct_name_spelling : str):

    # make the correct name an alias of the incorrect name
    if (incorrect_name_spelling.lower() != correct_name_spelling.lower()):
        add_player(incorrect_name_spelling) # add incorrect name to dictionary
        create_alias(incorrect_name_spelling, correct_name_spelling) # create the alias
        store_in_db_from_backlog([incorrect_name_spelling], True); # store the data in the backlog into the main db
    else:
        msg = "**[WARNING]** The old name and new names are the same, so the command was not run. Try using 'add' instead!"
        print(msg)

# confirm
# sends the data of any number of space delimited names in the backlog
# to the main database without checking power values
def confirm(name):
    store_in_db_from_backlog([name], False)

# status
# shows the number of names that have been successfully uploaded for
# a given team, and lists the names still in the backlog
# @param team, an alliance string
def status(team : str):
    cur = conn.cursor()
    sql = '''SELECT COUNT(*) FROM main  WHERE Alliance="{}" AND Date="{}"'''.format(team.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
    print('SQL: ' + sql)
    cur.execute(sql)
    num_data = cur.fetchone()
    if num_data is not None and num_data[0] > 0:
        sql = '''SELECT Name, Lv, Power FROM backlog WHERE Alliance="{}" AND Date="{}" AND reason=0'''.format(team.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
        print('SQL: ' + sql)
        cur.execute(sql)
        unrecognized_list = cur.fetchall()
        unrecognized_msgs = []
        for row in unrecognized_list:
            unrecognized_msgs.append("\tName: %s, Lv: %s, Power: %s" % (row[0], row[1], row[2]))
        sql = '''SELECT Name, Lv, Power FROM backlog WHERE Alliance="{}" AND Date="{}" AND reason=1'''.format(team.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
        print('SQL: ' + sql)
        cur.execute(sql)
        power_warn_list = cur.fetchall()
        power_warn_msgs = []
        for row in power_warn_list:
            power_warn_msgs.append("\tName: %s, Lv: %s, Power: %s" % (row[0], row[1], row[2]))
        sql = '''SELECT Name, Lv, Power FROM backlog WHERE Alliance="{}" AND Date="{}" AND reason=2'''.format(team.lower(), datetime.datetime.now().strftime("%Y-%m-%d"))
        print('SQL: ' + sql)
        cur.execute(sql)
        new_player_list = cur.fetchall()
        new_player_msgs = []
        for row in new_player_list:
            new_player_msgs.append("\tName: %s, Lv: %s, Power: %s" % (row[0], row[1], row[2]))
        msg = ''.join(("**Team {} Status**\n".format(team.upper()),
              "SUCCESS ({}): uploaded data for {} players today\n".format(num_data[0], num_data[0]),
              "UNRECOGNIZED NAMES ({}): {}\n".format( len(unrecognized_list),
                "the following players either have misspelled names or are new to the team.\n{}".format("\n".join(unrecognized_msgs)) if len(unrecognized_list) > 0 else "No mispelled names."
                ),
              "POWER WARNINGS ({}): {}\n".format( len(power_warn_list),
                "the following players have suspicious power values so their power values must be confirmed if they are correct.\n{}".format("\n".join(power_warn_msgs)) if len(power_warn_list) > 0 else "No power warnings."
                ),
              "NEW PLAYERS ({}): {}\n".format( len(new_player_list), "the following players have just joined the team so their power values must be confirmed if they are correct.\n{}".format("\n".join(new_player_msgs)) if len(new_player_list) > 0 else "No new players."
                )
        ))
        print(msg)
    else:
        msg = "No data has been uploaded for team {} today".format(team)
        print(msg)

# guess
# list all guesses for the specified player ordered first by level and then by power
# @param player, the name to guess
# @param limit, maximum number of guesses to make
def guess(player : str, limit=3):
    cur = conn.cursor()
    sql = '''SELECT Count(*) FROM backlog WHERE name="{}"'''.format(player.lower())
    cur.execute(sql)
    res = cur.fetchone()
    if res is None or len(res) == 0:
        msg = '''No such player is in the backlog'''
        print(msg)
        return

    sql = '''
        SELECT Name, Lv, Power, Date FROM
        (
            SELECT IFNULL(E.Name, D.Name) AS Name, C.Date, C.Lv, C.Power, IFNULL (A.Power - B.Power, 0) AS Diff, IFNULL (A.Lv - B.Lv, 0) AS Lv_diff
            FROM [backlog] A
                INNER JOIN [main] C
                    ON A.Alliance = C.Alliance
                    AND julianday(C.Date) < julianday(A.Date)
                    AND julianday(C.Date, '+7 days') > julianday(A.date)
                INNER JOIN
                (
                    SELECT key, MAX(Date) maxDate, Power, Lv
                    FROM [main]
                    GROUP BY key
                ) B ON C.key = B.key AND
                    C.Date = B.maxDate
            INNER JOIN
            (
                SELECT Name, key
                FROM [alias]
                WHERE active = 1
                GROUP BY key
            ) D ON C.key = D.key
            INNER JOIN
            (
                SELECT Name, key
                FROM [display]
                GROUP BY key
            ) E ON C.key = E.Key

            WHERE A.Name = "{}"


            ORDER BY ABS(Lv_diff), ABS(Diff) ASC
        )
        LIMIT "{}"
        '''.format(player.lower(), limit)
    print('SQL: ' + sql)
    cur.execute(sql)
    result = cur.fetchall()

    if result and len(result) > 0:
        msg = "Guesses for %s:\n" % player
        for row in result:
            msg += "\tName: {}, Lv: {}, Power: {}, Date: {}\n".format(row[0], row[1], row[2], row[3])
        print(msg)
    else:
        msg = "No guesses for %s" % player
        print(msg)

# missing
# list all the players that have data in the last week, but no data for today
# @param team, an alliance name string
def missing(team : str):
    cur = conn.cursor()
    sql = '''
        SELECT Name, Lv, Power, Date FROM
        (
            SELECT IFNULL(D.Name, C.Name) AS Name, A.Date, A.Lv, A.Power
            FROM [main] A
            INNER JOIN
            (
                SELECT key, MAX(Date) maxDate, Power, Lv
                FROM [main]
                WHERE julianday(Date, '+7 days') > julianday('now', 'localtime')
                GROUP BY key
            ) B ON A.key = B.key AND
                A.Date = B.maxDate AND
                B.maxDate != date('now', 'localtime') AND
                A.Alliance = "{}"
            INNER JOIN
            (
                SELECT Name, key
                FROM [alias]
                WHERE active = 1
                GROUP BY key
            ) C ON A.key = C.Key
            INNER JOIN
            (
                SELECT Name, key
                FROM [display]
                GROUP BY key
            ) D ON A.key = D.Key

        )
        ORDER BY Power DESC
        '''.format(team.lower())
    print('SQL: ' + sql)
    cur.execute(sql)
    result = cur.fetchall()

    if result and len(result) > 0:
        msg = "Missing players from %s:\n" % team
        for row in result:
            msg += "\tName: {}, Lv: {}, Power: {}, Date: {}\n".format(row[0], row[1], row[2], row[3])
        print(msg)
    else:
        msg = "No missing players. (Yay!)"
        print(msg)

# ------------------------------------------------------------------------------
#                                 MAIN SCRIPT
# ------------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('-u', '--upload', nargs='+')
parser.add_argument('-a', '--add', nargs='+')
parser.add_argument('-r', '--remove', nargs='+')
parser.add_argument('-t', '--time', action='store_true')
parser.add_argument('-c', '--correct', nargs=2)
parser.add_argument('--confirm', nargs=1)
parser.add_argument('-s', '--status', nargs=1)
parser.add_argument('-g', '--guess', nargs=1)
parser.add_argument('-m', '--missing', nargs=1)
args = parser.parse_args()
if args is False:
    print('Something went wrong. Stopping...')
elif not conn:
    print('Failed to connect to database. Stopping...')
else:
    if args.upload is not None:
        upload(args.upload[0], args.upload[1:])
    elif args.add is not None:
        for arg in args.add:
            add_player(arg)
    elif args.remove is not None:
        for arg in args.remove:
            remove_player(arg)
    elif args.time is True:
        time()
    elif args.correct is not None:
        correct(args.correct[0], args.correct[1])
    elif args.confirm is not None:
        confirm(args.confirm[0])
    elif args.status is not None:
        status(args.status[0])
    elif args.guess is not None:
        guess(args.guess[0])
    elif args.missing is not None:
        missing(args.missing[0])
