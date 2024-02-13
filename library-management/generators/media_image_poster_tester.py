import os
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
import json
import random
from fontTools.ttLib import TTFont, TTCollection
import argparse
import numpy as np



def processImage(font_name, media_object, image_path):

    # Get a list of all font files
    font_files = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

    # The name of the font you're looking for
    font_name_to_find = font_name

    # Get the path of the font
    font_path = None
    for font_file in font_files:
        try:
            # Try to open as a single font file
            font = TTFont(font_file)
            if font['name'].getDebugName(1) == font_name_to_find:
                font_path = font_file
                break
        except:
            # If that fails, try to open as a font collection file
            font_collection = TTCollection(font_file)
            for font in font_collection.fonts:
                if font['name'].getDebugName(1) == font_name_to_find:
                    font_path = font_file
                    break

    if font_path is None:
        font_path="Magneto.ttf"

    # Open an image file for manipulation
    with Image.open(image_path) as img:
        
        img_w, img_h = img.size

        # Get a random layout from posters.json
        with open(templates_base + "posters.json") as json_file:
            poster_json=json.load(json_file)
            poster_layout=random.choice(poster_json["layouts"])


        for text_type in poster_layout:
            layout = poster_layout[text_type]
            
            # Build out a cast layout if the text_type is cast from the template
            if text_type == "cast":
                #Randomly pull from list of 3 items
                #cast_type = random.choice(['actors','directors','full'])
                cast_type = layout[0]["cast_type"]
                text_string = ""
                if cast_type == "directors":
                    text_string += "Directed By "
                    for director in media_object["prompt_list"]["directors"]:
                        text_string += director + "   "
                elif cast_type == "actors":
                    actor_count=0
                    for actor in media_object["prompt_list"]["actors"]:
                        text_string += actor + "   "
                        actor_count += 1
                    if actor_count == 1:
                        text_string = "Starring: " + text_string
                else:
                    for actor in media_object["prompt_list"]["actors"]:
                        text_string += actor + "   "
                    text_string += ":: Directed By "
                    for director in media_object["prompt_list"]["directors"]:
                        text_string += director + "   "
            else:
                text_string = media_object[text_type]
            
            # Randomly choose to uppercase the text
            uppercase_chance = random.randint(1, 10)
            if uppercase_chance == 1:
                text_string = text_string.upper()

            #TODO maybe do some formatting for cast text if that is the layout text_type
            writeText(img, img_w, img_h, text_string, layout[0], font_path)


        img = img.resize((724, 1267))
        img = img.convert('RGB')
        img.save(image_path.replace('png', 'jpg'), 'JPEG', quality=75)
        img.show()


    return True

def writeText(img, img_w, img_h, text_string, layout, font_path): 
    
    draw = ImageDraw.Draw(img)

    # split the string on a delimeter into a list and find the biggest portion, keep the delimiter
    text_list = text_string.split(layout["delimiter"])
    max_text = max(text_list, key=len)
    
    # If the count of the delimiter in the string is 1 then add the delimtier back to the string
    if text_string.count(layout["delimiter"]) == 1:
        text_list[0] += layout["delimiter"]

    fontsize = 1  # starting font size
    font = ImageFont.truetype(font_path, fontsize)

    # Find  font size to fit the text based upon fraction of the image width and biggest string section
    while font.getlength(max_text) < layout["scale"]*img_w:
        # iterate until the text size is just larger than the criteria
        fontsize += 1
        font = ImageFont.truetype(font_path, fontsize)
    
    # Decrement to be sure it is less than criteria and styled
    fontsize -= layout["decrement"]
    font = ImageFont.truetype(font_path, fontsize)

    ascent, descent = font.getmetrics()
    # The height of the font is the delta of its ascent and descent
    font_height = ascent - descent

    section_top = 25 # Pad off the top of the image
    section_middle = (img_h / 2) - (font_height * len(text_list) + (layout["line_padding"] * len(text_list))) # Center of the image but offset by font and line count
    section_bottom = img_h - (img_h / 8) # bottom 1/8th of image
    y_placements = {"top": section_top, "middle": section_middle, "bottom": section_bottom}

    w = font.getlength(max_text)
    w_placement=(img_w-w)/2
    # Get the font's ascent and descent

    text_count = 1
    for text_line in text_list:

        # remove proceeding and trailing spaces
        text_line = text_line.strip()
        
        # Get the starting location for the text based upon the layout
        y_start = y_placements[layout["y_placement"]]
        
        y_placement = y_start + ((font_height) * (text_count - 1))
        if text_count > 1:
            y_placement = y_placement + (layout["line_padding"] * (text_count - 1))

        sample_box = (w_placement, y_placement, w_placement + w, y_placement + font_height)
        crop = img.crop(sample_box)
        pixels = np.array(crop)
        average_color = pixels.mean(axis=(0, 1))

        average_color = tuple(map(int, average_color))
        #complimentary_color = tuple(255 - x for x in average_color)
        color_average = sum(average_color) / len(average_color)
        if color_average < 60:
            r_comp = 255
            g_comp = 255
            b_comp = 255
            stroke_color='grey'
        elif color_average > 200:
            r_comp = 125
            g_comp = 125
            b_comp = 125
            stroke_color='black'
        else:
            r_comp = 0
            g_comp = 0
            b_comp = 0
            stroke_color='white'

        # # Get the average of the RGB values
        # complimentary_average = (255 - (sum(complimentary_color) / len(complimentary_color)))
        # if complimentary_average < 75:
        #     r_comp = 0
        #     g_comp = 0
        #     b_comp = 0
        #     stroke_color='white'
        # elif complimentary_average > 200:
        #     r_comp = 255
        #     g_comp = 255
        #     b_comp = 255
        #     stroke_color='black'
        # else:
        #     r_comp = complimentary_color[0]
        #     g_comp = complimentary_color[1]
        #     b_comp = complimentary_color[2]
        #     stroke_color='black'

                    
        
        # hex_color = '#{:02x}{:02x}{:02x}'.format(complimentary_color[0]+complimentary_average, complimentary_color[1]+complimentary_average, complimentary_color[2]+complimentary_average)
        hex_color = '#{:02x}{:02x}{:02x}'.format(r_comp, g_comp, b_comp)

        draw.text((w_placement, y_placement), text_line, fill=hex_color, font=font, stroke_width=1, stroke_fill=stroke_color) # put the text on the image
        
        text_count += 1

    return img

# For command line arguments
parser = argparse.ArgumentParser(description="Provide various run commands.")
# Argument for the count of media objects to generate
parser.add_argument("-s", "--short", action='store_true', help="Use Short prompt")
parser.add_argument("-l", "--long", action='store_true', help="Use Long prompt")
args = parser.parse_args()


if args.short:
    media_object_path = os.path.join(os.getcwd(), "outputs/media/sample_short.json")
else:
    media_object_path = os.path.join(os.getcwd(), "outputs/media/sample_long.json")

templates_base = os.getcwd() + "/library-management/templates/"

with open(media_object_path) as json_file:
    media_object = json.load(json_file)

processImage(media_object["image_font"], media_object, os.getcwd() + "/outputs/media/image_template.png")