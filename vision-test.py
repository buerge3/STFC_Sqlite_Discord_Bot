#!/usr/bin/env python
#
# FILENAME: vision-test.py
# CREATED:	August 17, 2019
# AUTHOR:	buerge3
#
# A command-line script for testing image-processing functionality indpendentent
# of sqlite or discord. Expects a screenshot of an STFC roster as the first
# command-line argument.
# Usage: "python ./vision-test.py <image_file_path>"

from PIL import Image
import pytesseract
import math
from spellchecker import SpellChecker
import re
import sys

# MODIFIABLE PARAMTERS
img_path = sys.argv[1]
x_percent = 14

# -----------------------------------------------------------------------------
#                                    FUNCTIONS
# -----------------------------------------------------------------------------
# IsImage
# @return true if the first command-line argument is an image
def isImage():
	return img_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'))

# get_rgb_filter
# @param im, the STFC roster screenshot to find appropriate filter values for
# @returns rgb, a three-element list consisting of the rgb values for the filter
def get_rgb_filter(im):
	width, height = im.size
	rgb = [220, 220, 220]
	for i in range(3):
		im_rgb = im.crop((0, 0, width, math.floor(height/10)))
		print("trying r=" + str(rgb[0]), ", g=" + str(rgb[1]) + ", b=" + str(rgb[2]))
		apply_img_mask(im_rgb, rgb, x_percent)
		word = pytesseract.image_to_string(im_rgb)
		#print("I read: " + word)
		if (bool(re.search(r"MEM", word))):
			print("found a working filter! I see: " + word)
			return rgb;
		else:
			rgb[0] -= 20
			rgb[1] -= 20
			rgb[2] -= 20
	print("Unable to process screenshot. I only see: " + word)
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
def process_image(im, names_list, level_list):
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
        	if (tmp.strip()):
	            names_list.append(tmp)
	            success = True
        else:
            names_list.append("DELETE_ME")
            level_list.append(0)
    if not success:
        msg = "Unable to process image; cause: did not identify any rows";
        print(msg)
    if len(names_list) != len(level_list):
        msg = "Unable to process image; cause: did not identify exactly one level for each name"
        print(msg)
        print("NAMES:")
        for name in names_list:
            print(name)
        print("LEVELS:")
        for lv in level_list:
            print(lv)
    return True;

# check_spelling
# @param names_list, a list of player names to check the spelling of
#         using the dictionary file 'STFC_dict.txt'
def check_spelling(names_list):
    spell = SpellChecker(language=None, case_sensitive=False)
    spell.word_frequency.load_text_file("STFC_dict.txt")
    
    for i in range(len(names_list)):
        if (names_list[i] == "DELETE_ME"):
            continue
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
if not isImage():
    print('Please only submit images. Stopping...')
else:
	im = Image.open(img_path).convert("RGB") 
	pixdata = im.load()
	width, height = im.size
	x_cutoff = math.floor(width / x_percent)
	names_list = []
	level_list = []
	rgb = get_rgb_filter(im)
	if (rgb is not None):
		apply_img_mask(im, rgb, x_percent)
		#im.show()
		if (process_image(im, names_list, level_list)):
		    check_spelling(names_list)
		    width, height = im.size
		    power_list = []
		    im_power = im.crop((math.floor(width/2), math.floor(height/10), width, height))
		    power = pytesseract.image_to_string(im_power)
		    power_list = power.split('\n')
		    for i in range(len(power_list)):
		    	power_list[i] = re.sub("[^0-9]", "", power_list[i])
		    power_list = list(filter(None, power_list))
		    store_in_db(names_list, level_list, power_list, "TEST")
		else:
			im.show()
