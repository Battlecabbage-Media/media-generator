from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import requests
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
import json
import random
from fontTools.ttLib import TTFont, TTCollection
import argparse
import datetime
import numpy as np


# REQUIREMENTS
# pip install matplotlib
# pip install python-dotenv
# pip install openai
# pip install pillow

load_dotenv()

# TODO:
# 2. Implement the ability to generate a response without saving it to a file, dry run
# 3. Implement checks for failures and move forward. If a failure occurs, log the prompt and response to a file for review, potenitally retrying the prompt a few times before moving on.
# 5. Ability to add a logo to the poster like the rating
# 6. Format the font to have better readability. Maybe on complimentary color, outlines, etc.
# 7. Proper checks if certain values came back from completion, example critic_score
# 8. Check for letterbox image and regenerate, Cameron?
# 9. Fix lq flag to work properly, keeps failing size, I blame Dalle3, works with 1024x1024 not 512x512


# Check if the image has already been generated
def checkImage(images_directory,image_id):
    if os.path.isfile(images_directory + image_id + ".jpg"):
        return True
    else:
        return False


#TODO separate in directory file types
# Find all media objects that dont have an associated .jpg image file
def imageBuildList(media_directory):

    json_files = []
    # jpg_files = []
    png_files = []

    # Iterate over all subdirectories in main generated media directory
    for root, dirs, files in os.walk(media_directory):

        json_files += [os.path.join(root, f) for f in files if f.endswith('.json')]
        # jpg_files += [os.path.join(root, f) for f in files if f.endswith('.jpg')]
        png_files += [os.path.join(root, f) for f in files if f.endswith('.png')]
    
    # Check if there is a .jpg file that matches the same name as a .json file
    missing_images = []
    for json_file in json_files:

        base_file = os.path.basename(json_file)
        # Construct the path to the .jpg file in the 'images' folder
        jpg_file_path = os.path.join(os.path.dirname(json_file), "images", os.path.basename(json_file).replace(".json", ".jpg"))
        # Check if a .jpg file exists
        if not os.path.exists(jpg_file_path):
            missing_images.append(json_file)

    return missing_images, png_files      



# Generate the prompt for the image based upon the media object info
def generateImagePrompt(media_object):
    
    # Create the AzureOpenAI client for image prompt
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT_KEY"),  
        api_version=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION"),
        azure_endpoint = os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    )
    deployment_name=os.getenv("AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME")
    
    # Get a list of all font files
    font_files = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

    # Get a list of all font names
    font_names = []
    for font_file in font_files:
        try:
            # Try to open as a single font file
            font = TTFont(font_file)
            font_names.append(font['name'].getDebugName(1))
        except:
            # If that fails, try to open as a font collection file
            font_collection = TTCollection(font_file)
            for font in font_collection.fonts:
                font_names.append(font['name'].getDebugName(1))

    # trim the list to 25 random fonts
    if len(font_names) > 50:
        font_names = random.sample(font_names, 50)  

    # TODO: Add error handling for failed requests
    # Send the description to the API
    with open(templates_base + "prompts.json") as json_file:

        prompt_json=json.load(json_file)
        prompt_image_json=random.choice(prompt_json["prompts_image"])
    
        #remove objects from media_object that are not needed for the prompt

        object_keys_keep = ["title", "tagline", "mpaa_rating", "description"]
        media_object ={k: media_object[k] for k in object_keys_keep}
        media_object=json.dumps(media_object)

        full_prompt = prompt_image_json + json.dumps(media_object) + ",{'font_names':" + json.dumps(font_names)
        if args.verbose: print(f"{str(datetime.datetime.now())} -  Prompt\n" + full_prompt)
        response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":full_prompt}], max_tokens=500, temperature=0.7)
        completion=response.choices[0].message.content

        # Find the start and end index of the json object
        start_index = completion.find("{")
        end_index = completion.find("}")
        completion = json.loads(completion[start_index:end_index+1])
        
        if args.verbose: print(f"{str(datetime.datetime.now())} - Completion \n {json.dumps(completion, indent=4)}")

        return completion
    

# Generate the image using the prompt
def generateImage(file_path, image_prompt, media_object):

    client = AzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_DALLE3_API_VERSION"),  
        api_key=os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT")
    )

    i_range = 5
    for attempt in range(i_range):
        try:
            result = client.images.generate(
                model=os.getenv("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME"), # the name of your DALL-E 3 deployment
                prompt=image_prompt["image_prompt"],
                n=1,
                size="1024x1024" if args.low_quality else "1024x1792"
            )
            break
        except Exception as e:
            if args.verbose: print(f"{str(datetime.datetime.now())} - Attempt {attempt+1} of {i_range} failed to generate image for {media_object['title']}, ID: {media_object['id']}.")
            if args.verbose: print(f"Error: {e}")
    else:
        return False, "FAILED"

    # Grab the first image from the response
    json_response = json.loads(result.model_dump_json())

    # Retrieve the generated image and save it to the images directory
    image_url = json_response["data"][0]["url"]  # extract image URL from response
    generated_image = requests.get(image_url).content  # download the image
    
    file_path=file_path.replace(f"{media_object["id"]}.json",f"/images/{media_object["id"]}.png")

    #Get the directory of file path

    
    # TODO: Check if the image is letterboxed and retry if it is
    # # Open the image
    # img = Image.open(generated_image)
    # # Define the section (top left x, top left y, bottom right x, bottom right y)
    # section = (10, 10, 50, 50)
    # # Crop the section from the image
    # crop = img.crop(section)
    # # Get the color of the first pixel
    # first_pixel_color = crop.getpixel((0, 0))
    # # Check if all pixels have the same color
    # is_same_color = all(crop.getpixel((x, y)) == first_pixel_color for x in range(crop.width) for y in range(crop.height))
    # if is_same_color:
    #     print(f"Image {media_object['id']} is letterboxed, retrying.")
    #     #Resubmit the image. There could be concern of an infinite loop here, but the likelihood is low since letterboxing rarely happens
    #     generateImage(file_path, image_prompt, media_object) 

     # Create the images directory if it does not exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, "wb") as image_file:
            image_file.write(generated_image)
            return True, file_path
    except:
        print(f"Error saving image {media_object['id']}.png")
        return False, "FAILED"
    

# Add various text to the image and resize
def processImage(completion, media_object, image_path):

    # Get a list of all font files
    font_files = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

    # The name of the font you're looking for
    font_name_to_find = completion["font"]

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
        font_path="arial.ttf"

    # Open an image file for manipulation
    with Image.open(image_path) as img:
        
        img_w, img_h = img.size

        # Get a random layout from posters.json
        with open(templates_base + "posters.json") as json_file:
            poster_json=json.load(json_file)
            poster_layout=random.choice(poster_json["layouts"])

        # loop through the layout and print out each text_type
        for text_type in poster_layout:
            layout = poster_layout[text_type]
            
            # Build out a cast layout if the text_type is cast from the template
            if text_type == "cast":
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

            writeText(img, img_w, img_h, text_string, layout[0], font_path)

        # TODO rethink the qhole quality thing, if even needed.
        if not args.low_quality:
            img = img.resize((724, 1267))
            img = img.convert('RGB')
            img.save(image_path.replace('png', 'jpg'), 'JPEG', quality=75)
            #Delete the original png file
            os.remove(image_path)
        else:
            img.save(image_path, 'PNG')

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
        color_average = sum(average_color) / len(average_color)
        if color_average < 60:
            r_comp = 255
            g_comp = 255
            b_comp = 255
            stroke_color="#9A9A9A"
        elif color_average > 200:
            r_comp = 125
            g_comp = 125
            b_comp = 125
            stroke_color="#101010"
        else:
            r_comp = 0
            g_comp = 0
            b_comp = 0
            stroke_color="#CDCDCD"
                    
        
        # hex_color = '#{:02x}{:02x}{:02x}'.format(complimentary_color[0]+complimentary_average, complimentary_color[1]+complimentary_average, complimentary_color[2]+complimentary_average)
        hex_color = '#{:02x}{:02x}{:02x}'.format(r_comp, g_comp, b_comp)

        draw.text((w_placement, y_placement), text_line, fill=hex_color, font=font, stroke_width=1, stroke_fill=stroke_color) # put the text on the image
        
        text_count += 1

    return img

def main():

    processed_count=0
    created_count=0

    # Get list of all media objects missing a poster, and orphaned png posters files 
    # TODO variable, you know how to do it   
    missing_list, png_list = imageBuildList(os.getcwd() + "/outputs/media/generated/")
    #print(missing_list)
    #exit()

    if len(png_list) > 0:
        print(f"{str(datetime.datetime.now())} - Orphaned PNG files found, quick housekeeping.")
        for png_file in png_list:
            os.remove(png_file)

    missing_count = len(missing_list)

    if missing_count > 0:
        print(f"{str(datetime.datetime.now())} - Starting Media Image generation, Total Missing: {missing_count}")
        for filepath in missing_list:

            if args.single and processed_count > 0: 
                print(f"{str(datetime.datetime.now())} - Single image processing mode enabled, skipping additional media objects.")
                exit()

            with open(filepath, 'r') as file:
                media_object = json.load(file)

                print(f"{str(datetime.datetime.now())} - Generating Image for {media_object["title"]}, ID: {media_object["id"]}")

                if args.verbose:print(f"{str(datetime.datetime.now())} - Generating Image Prompt for {media_object["title"]}, ID: {media_object["id"]}")
                completion=generateImagePrompt(media_object)
                if args.verbose: print(f"{str(datetime.datetime.now())} - Image Prompt Generated for {media_object["title"]}, ID: {media_object["id"]} \nImage Prompt:\n{completion["image_prompt"]}")

                result, image_path = generateImage(filepath, completion, media_object)
                if result == True:
                    processImage(completion, media_object, image_path)
                    print(f"{str(datetime.datetime.now())} - Image created for {media_object["title"]}")
                    if args.verbose: print(f"Location: {str(image_path.replace('.png','.jpg'))}")
                    
                    # Save image completion and image generate date to media object file
                    with open(filepath, 'w') as updated_file:
                        media_object["image_generation_time"] = str(datetime.datetime.now())
                        media_object["image_prompt"] = completion["image_prompt"].replace("'", "\"")
                        media_object["image_font"] = completion["font"]
                        media_object["azure_openai_image_model_endpoint"] = os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT")
                        media_object["azure_openai_image_model_deployment"] = os.getenv("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME")
                        media_object["azure_openai_image_model_api_version"] = os.getenv("AZURE_OPENAI_DALLE3_API_VERSION")
                        file.seek(0)
                        json.dump(media_object, updated_file, indent=4)

                    created_count+=1
                else:
                    print(f"{str(datetime.datetime.now())} - Failed to generate image for {media_object["title"]} ID: {media_object["id"]}")
                
                processed_count+=1
                print(f"{str(datetime.datetime.now())} - Media Objects Processed: {str(processed_count)} of {str(missing_count)}")

        message = f"{str(datetime.datetime.now())} - All media objects reviewed."
        if processed_count > 0: 
            message += f" Image Create Count: {str(created_count)}, Processed Count: {str(processed_count)}"
            print(message)
    else:
        print(f"{str(datetime.datetime.now())} - No media objects missing images.")


load_dotenv()
working_dir=os.getcwd()
objects_directory = working_dir + "/outputs/media/objects/"
images_directory = working_dir + "/outputs/media/images/"
templates_base = working_dir + "/library-management/templates/"
outputs_dir = "outputs/media/"

# For command line arguments
parser = argparse.ArgumentParser(description="Provide various run commands.")
# Argument for the count of media objects to generate
parser.add_argument("-c", "--count", help="Number of media objects to generate")
# Argument for the dry run, to generate a response without saving it to a file
parser.add_argument("-d", "--dryrun", action='store_true', help="Dry run, generate a response without saving it to a file")
# Argument for verbose mode, to display object outputs
parser.add_argument("-v", "--verbose", action='store_true', help="Show object outputs like prompts and completions")
parser.add_argument("-s", "--single", action='store_true', help="Only process a single image, for testing purposes")
parser.add_argument("-lq", "--low_quality", action='store_true', help="Create low quality images for testing.")
args = parser.parse_args()


#imageBuildList(os.getcwd() + "/outputs/media/generated/")
# Run the main loop
main()