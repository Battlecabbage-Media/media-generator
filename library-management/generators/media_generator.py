import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import random
import hashlib
import argparse
import datetime
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
from fontTools.ttLib import TTFont, TTCollection
import argparse
import datetime
import requests
from io import BytesIO
from mimetypes import guess_type
import base64
import traceback

# REQUIREMENTS
# pip install python-dotenv
# pip install openai

# TODO - Add proper error handling for failed requests, try/except blocks

# Simply grabs a random value from the template file provided
def getTemplateValue(template):
    with open(templates_base + template + ".json") as json_file:
        return random.choice(json.load(json_file)[template])

# Parses the prompt template and replaces the values with the random values from the template file
def parseTemplate(template, object_prompt_list):

    start_index = template.find("{")
    while start_index != -1:
        end_index = template.find("}")
        text = template[start_index+1:end_index]
        replace_value=getTemplateValue(text)
        template = template.replace("{"+text+"}", replace_value,1)
        if text not in object_prompt_list:
            object_prompt_list[text] = []
        object_prompt_list[text].append(replace_value)
        start_index = template.find("{")
    return template, object_prompt_list

def getOutputPath(type, id):
    now = datetime.datetime.now()
    base_dir=os.path.join(os.getcwd(),outputs_dir)
    date_depth="%Y/%m/%d"#/%H/%M/%S"
   
    if type == "image":
        file_path = os.path.join(base_dir, now.strftime(date_depth),"images", f"{id}.jpg")
    else:
        file_path = os.path.join(base_dir, now.strftime(date_depth),"objects", f"{id}.json")

    return file_path

# Builds the prompt from the prompt template selected
def generateObjectPrompt():

    object_prompt_list={}
    with open(templates_base + "prompts.json") as json_file:

        # Load the prompt template file and parse the prompt template
        prompt_json=json.load(json_file)
        prompt_start, object_prompt_list=parseTemplate(random.choice(prompt_json["prompts_start"]), object_prompt_list)
        prompt_cast, object_prompt_list=parseTemplate(random.choice(prompt_json["prompts_cast"]), object_prompt_list)
        prompt_synopsis, object_prompt_list=parseTemplate(random.choice(prompt_json["prompts_synopsis"]), object_prompt_list)
        prompt_end, object_prompt_list=parseTemplate(random.choice(prompt_json["prompts_end"]), object_prompt_list)
        prompt=f"{prompt_start} {prompt_cast} {prompt_synopsis} {prompt_end}"

        return prompt, object_prompt_list

# Submits the prompt to the API and returns the response as a formatted json object
def generateObject(object_prompt, object_prompt_list):

    # Create the AzureOpenAI client
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT_KEY"),  
        api_version=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION"),
        azure_endpoint = os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    )
    deployment_name=os.getenv("AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME")
    
    # TODO: Add error handling for failed requests
    # Send the prompt to the API
    response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":object_prompt}], max_tokens=500, temperature=0.7)

    # Parse the response and return the formatted json object
    completion=response.choices[0].message.content

    # Find the start and end index of the json object
    start_index = completion.find("{")
    end_index = completion.find("}")
    completion = json.loads(completion[start_index:end_index+1])

    # Create a hash ID for the media object based upon the title
    hash_object = hashlib.md5()
    hash_object.update(completion["title"].encode())
    media_id = hash_object.hexdigest()[:12]

    # TODO proper error handling if any of the completion values are missing
    media_object = { 
            "id":media_id,
            "title":completion["title"],
            "tagline":completion["tagline"],
            "mpaa_rating":completion["mpaa_rating"],
            "mpaa_rating_content":completion["rating_content"],
            "critic_score":completion["critic_score"],
            "critic_review":completion["critic_review"],
            "popularity_score":round(random.uniform(1, 10), 1),
            "genre":completion["genre"],
            "description":completion["description"],
            "poster_url":"movie_poster_url.jpeg",
        }
    
    media_object["object_prompt"]=object_prompt
    media_object["object_prompt_list"]=object_prompt_list
    media_object["azure_openai_text_completion_endpoint"]=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    media_object["azure_openai_text_completion_deployment_name"]=deployment_name
    media_object["azure_openai_text_completion_api_version"]=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION")

    return json.dumps(media_object)

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
def generateImage(image_completion, media_object):

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
                prompt=image_completion["image_prompt"],
                n=1,
                size="1024x1792"
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
    generated_image = BytesIO(requests.get(image_url).content)  # download the image
    
    return True, generated_image

# Add text to the image and resize
def processImage(generated_image, image_completion, media_object):

    # Get a list of all font files
    font_files = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

    # The name of the font you're looking for
    font_name_to_find = image_completion["font"]
    
    # Start with arial as the default font
    font_path="arial.ttf"

    # Get the path of the font
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
            

    # Open prompt file and parse the prompt
    with open(templates_base + "prompts.json") as json_file:
        prompt_json=json.load(json_file)
    
    prompt=prompt_json["vision"][0]
    start_index = prompt.find("{")
    while start_index != -1:
        end_index = prompt.find("}")
        key = prompt[start_index+1:end_index]
        key_value = media_object[key] if key in media_object else image_completion[key] # Value for template replacement should exist in either media_object or completion
        prompt = prompt.replace("{"+key+"}", key_value,1)
        start_index = prompt.find("{")

    # # Guess the MIME type of the image based on the file extension
    # mime_type, _ = guess_type(generated_image)
    # if mime_type is None:
    #     mime_type = 'application/octet-stream'  # Default MIME type if none is found
    mime_type = "image/png"
    base64_encoded_data = base64.b64encode(generated_image.read()).decode('utf-8')

    api_base = os.getenv("AZURE_OPENAI_GPT4_VISION_ENDPOINT")
    api_key=os.getenv("AZURE_OPENAI_GPT4_VISION_ENDPOINT_KEY")
    deployment_name = os.getenv("AZURE_OPENAI_GPT4_VISION_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_GPT4_VISION_API_VERSION")

    client = AzureOpenAI(
        api_key=api_key,  
        api_version=api_version,
        base_url=f"{api_base}openai/deployments/{deployment_name}/extensions",
    )

    try:

        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                { "role": "system", "content": prompt_json["vision_system"] },
                { "role": "user", "content": [  
                    { 
                        "type": "text", 
                        "text": prompt 
                    },
                    { 
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_encoded_data}"
                        }
                    }
                ] } 
            ],
            max_tokens=2000 
        )

        vision_completion = response.choices[0].message.content

        # Find the start and end index of the json object
        start_index = vision_completion.find("{")
        end_index = vision_completion.find("}")
        vision_completion = json.loads(vision_completion[start_index:end_index+1])
        text_string = media_object["title"]
    
        # Randomly choose to uppercase the text
        uppercase_chance = random.randint(1, 10)
        if uppercase_chance == 1:
            text_string = text_string.upper()

        # split the string on a delimeter into a list and find the biggest portion, keep the delimiter
        delimiter = ":"
        text_list = text_string.split(delimiter)
        # If the count of the delimiter in the string is 1 then add the delimtier back to the string
        if text_string.count(delimiter) == 1:
            text_list[0] += delimiter
        max_text = max(text_list, key=len)

        # Open the image file for manipulation
        with Image.open(generated_image) as img:
            
            img_w, img_h = img.size
            draw = ImageDraw.Draw(img)

            fontsize = 1  # starting font size
            font = ImageFont.truetype(font_path, fontsize)
            # Find font size to fit the text based upon fraction of the image width and biggest string section
            scale=.85
            while font.getlength(max_text) < scale*img_w:
                # iterate until the text size is just larger than the criteria
                fontsize += 1
                font = ImageFont.truetype(font_path, fontsize)
            
            # Decrement to be sure it is less than criteria and styled
            fontsize -= 1
            font = ImageFont.truetype(font_path, fontsize)
            
            # The height of the font is the delta of its ascent and descent
            ascent, descent = font.getmetrics()
            font_height = ascent - descent

            section_top =  vision_completion["location_padding"]
            section_middle = (img_h / 2) - (font_height * len(text_list) + (20 * len(text_list))) # Center of the image but offset by font, line count and general padding
            section_bottom = img_h - (img_h / 8)
            section_bottom = section_bottom - font_height if len(text_list) > 1 else section_bottom # shave off one font height if there are two lines of text
            y_placements = {"top": section_top, "middle": section_middle, "bottom": section_bottom}

            w = font.getlength(max_text)
            w_placement=(img_w-w)/2

            line_count = 1
            for text_line in text_list:

                # remove proceeding and trailing spaces
                text_line = text_line.strip()
            
                # Get the starting location for the text based upon the layout
                y_location = vision_completion["location"] if "location" in vision_completion else "top"
                if line_count == 1:
                    y_placement = y_placements[y_location]
                else:
                    y_placement = y_placements[y_location] + (font_height * (line_count - 1)) + (font_height * .60) 

                font_color = vision_completion["font_color"] if "font_color" in vision_completion else "#000000"
                stroke_color = "#111111" if font_color > "#999999" else "#DDDDDD"

                # put the text on the image
                draw.text((w_placement, y_placement), text_line, fill=font_color, font=font, stroke_width=1, stroke_fill=stroke_color, align='center') 
                line_count += 1

            #img = img.resize((724, 1267))
            #img = img.convert('RGB')
            #img.save(getOutputPath("image", media_object["id"]), 'JPEG', quality=75)


        return True, img
    
    except Exception as e:
        print(f"Error processing image: {e}")
        traceback.print_exc()
        return False, e

# Creates a directory based upon the directory path provided
def createDirectory(directory):

    try:
        os.makedirs(directory, exist_ok=True)
    except:
        print(f"Error creating directory {directory}.")
        return False

    return True

def saveItem(item, type, item_id):

    item_path = getOutputPath(type, item_id)
    folder_path = os.path.dirname(item_path) 
    result = createDirectory(folder_path)
    if result == True:
        try:
            if type == "image":
                item = item.convert('RGB').resize((724, 1267))
                item.save(item_path, 'JPEG', quality=75)
            elif type == "json":
                with open(item_path, "w") as json_file:
                    json.dump(item, json_file)
                    json_file.write("\n")
            return True, item_path
        except Exception as e:
            print(f"Error saving {type} for media object {id}.\n{e}")
            return False, item_path
    else:
        return False, item_path


# Main function to run the generator
def main():

    start_time=datetime.datetime.now()
    # Check if a count command line value is provided and is a digit, if not default to 1
    if(args.count):
        if(args.count.isdigit()):
            generate_count=int(args.count)
        else:
            print("Invalid count provided, defaulting to 1")
            generate_count=1
    else:
        generate_count=1
    
    # Notify if dry run mode is enabled
    if(args.dryrun): print("\nDry run mode enabled, generated media objects will not be saved")

    # Main loop to generate the media objects
    i=0
    while i < generate_count:


        object_start_time = datetime.datetime.now()
        # Print the current media count being generated
        print(f"{str(datetime.datetime.now())} - Generating media object: {str(i+1)} of {str(generate_count)}")

        # Build the prompt and print it
        if args.verbose: print(f"{str(datetime.datetime.now())} - Building object prompt")
        object_prompt, object_prompt_list=generateObjectPrompt()
        if args.verbose: 
            print(f"{str(datetime.datetime.now())} - Finished building prompt, build time: {str(datetime.datetime.now() - object_start_time)}")
            print(f"Object prompt:\n {object_prompt}")
            print(f"Template list:\n {json.dumps(object_prompt_list, indent=4)}")

        # Submit the object prompt for completion and print the object completion
        print(f"{str(datetime.datetime.now())} - Submitting media prompt for completion")
        media_object=json.loads(generateObject(object_prompt, object_prompt_list))
        if args.verbose:
            print(f"{str(datetime.datetime.now())} - Object completion received, completion generate time: {str(datetime.datetime.now() - object_start_time)}")
            print("Object completion:\n" + json.dumps(media_object, indent=4)) # Print the completion
        
        print(f"{str(datetime.datetime.now())} - Finished generating media object {media_object['title']}, object generate time: {str(datetime.datetime.now() - object_start_time)}")

        image_start_time = datetime.datetime.now()
        print(f"{str(datetime.datetime.now())} - Creating image for {media_object["title"]}")
        print(f"{str(datetime.datetime.now())} - Generating image prompt for {media_object["title"]}")
        image_completion=generateImagePrompt(media_object)
        if args.verbose: 
            print(f"{str(datetime.datetime.now())} - Image prompt generated for {media_object["title"]}, image prompt generate time: {str(datetime.datetime.now() - image_start_time)}")
            print(f"Image prompt:\n{image_completion["image_prompt"]}")

        print(f"{str(datetime.datetime.now())} - Generating image for {media_object["title"]} from prompt")
        result, generated_image = generateImage(image_completion, media_object)
        if result == True:

            result, image = processImage(generated_image, image_completion, media_object)
            print(f"{str(datetime.datetime.now())} - Image created for {media_object["title"]}, image generate time: {str(datetime.datetime.now() - image_start_time)}")

            if result == True:
                media_object["image_generation_time"] = str(datetime.datetime.now())
                media_object["image_prompt"] = image_completion["image_prompt"].replace("'", "\"")
                media_object["image_font"] = image_completion["font"] if "font" in image_completion else "arial"
                media_object["azure_openai_image_model_endpoint"] = os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT")
                media_object["azure_openai_image_model_deployment"] = os.getenv("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME")
                media_object["azure_openai_image_model_api_version"] = os.getenv("AZURE_OPENAI_DALLE3_API_VERSION")
                
                # Save the media object and image to the outputs directory
                result, item_path = saveItem(media_object, "json", media_object["id"]) # Save Media JSON
                if result == True:
                    result, item_path = saveItem(image, "image", media_object["id"]) # Save Poster Image
                    if result == True:
                        print(f"{str(datetime.datetime.now())} - Media created: {media_object["title"]}, Id: {media_object["id"]}, generate time: {str(datetime.datetime.now() - object_start_time)}")
          
        i+=1

    print(f"{str(datetime.datetime.now())} - Finsished generating {str(generate_count)} media object(s) of {generate_count}, Total Time: {str(datetime.datetime.now() - start_time)}")

load_dotenv()
working_dir=os.getcwd()
templates_base=working_dir + "/library-management/templates/"
outputs_dir="outputs/media/generated/"

# For command line arguments
parser = argparse.ArgumentParser(description="Provide various run commands.")
# Argument for the count of media objects to generate
parser.add_argument("-c", "--count", help="Number of media objects to generate")
# Argument for the dry run, to generate a response without saving it to a file
parser.add_argument("-d", "--dryrun", action='store_true', help="Dry run, generate a response without saving it to a file")
# Argument for verbose mode, to display object outputs
parser.add_argument("-v", "--verbose", action='store_true', help="Show details of steps and outputs like prompts and completions")
args = parser.parse_args()


if __name__ == "__main__":
    main()