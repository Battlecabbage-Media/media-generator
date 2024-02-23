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
import requests
from io import BytesIO
import base64
import traceback

# REQUIREMENTS
# pip install python-dotenv
# pip install openai

def envCheck(env_var):
    if os.getenv(env_var) is None:
        outputMessage(f"Environment variable {env_var} not set. Check '.example.env' for details.","error")
        exit(1)

# Output message function to print the message with a timestamp and process ID
def outputMessage(message, level):
    
    if level == "error":
        color = "\033[91m" # Red
    elif level == "success":
        color = "\033[92m" # Green
    elif level == "info":
        color = "\033[94m" # Blue
    elif level == "warning":
        color = "\033[93m"  # Yellow
    elif level == "debug":
        color = "\033[95m"  # Purple
    elif level == "verbose":
        color = "\033[96m"  # Cyan
    else:
        color = "\033[0m" # white

    print(f"{str(datetime.datetime.now())} - {process_id} - {color}{message}")
    print("\033[0m", end="") # Reset color

# Creates a random process ID for the generator
def createProcessId():
    process_id = hashlib.md5(str(random.random()).encode()).hexdigest()[:16]
    return process_id
    
# Simply grabs a random value from the template file provided
def getTemplateValue(template):
    try:
        with open(f"{templates_base}{template}.json") as json_file:
            return random.choice(json.load(json_file)[template])
    except IOError as e:
        outputMessage(f"Error opening template file {template}.json: {e}", "error")
        exit()
    except Exception as e:
        outputMessage(f"An error occurred for {template}.json: {e}", "error")
        return False

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

# Builds the output path for the media object based upon the type and id
def getOutputPath(type, id, ext):
    now = datetime.datetime.now()
    base_dir=os.path.join(os.getcwd(),outputs_dir)
    date_depth="%Y/%m/%d"#/%H/%M/%S"
   
    file_path = os.path.join(base_dir, now.strftime(date_depth),type, f"{id}.{ext}")

    return file_path

# Extracts text from a string based upon the start and end values
def extractText(text, start, end):
    start_index = text.find(start)
    end_index = text.find(end)
    return text[start_index:end_index+1]

# Builds the prompt from the prompt template selected
def generateObjectPrompt():

    try:
        prompt_file = open(templates_base + "prompts.json", 'r')
    except IOError as e:
        outputMessage(f"Error opening prompt file. {templates_base}prompts.json. Check that it exists!", "error")
        exit()
    except Exception as e:
        outputMessage(f"An issue occurred building the object prompt: {e}", "error")
        return False, "An error occurred."
    except:
        outputMessage(f"Error opening prompt file. {templates_base}prompts.json. Check that it exists!","error")
        exit(1)

    # Load the prompt template file and parse the prompt template
    object_prompt_list={}
    prompt_json=json.load(prompt_file)
    prompt_file.close()
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
    
    # Send the prompt to the API
    try:
        temperature=round(random.uniform(0.6,1.1),2)
        response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":object_prompt}], max_tokens=600, temperature=temperature) # Going with random temperature for funsies
    except Exception as e:
        outputMessage(f"Error generating object : {e}", "error")
        if args.verbose: traceback.print_exc()
        return False

    # Parse the response and return the formatted json object
    completion=response.choices[0].message.content

    # Find the start and end index of the json object
    try:
        completion = json.loads(extractText(completion, "{", "}"))
    except:
        outputMessage(f"Error parsing object completion: {completion}","error")
        return False

    # use the process_id for the media_id
    media_id = process_id

    # We need to check if the title, tagline and description exists in the completion, if not we cant use the completion for later purposes

    if "title" in completion and "tagline" in completion and "description" in completion:
        media_object = { 
                "id":media_id,
                "title":completion["title"],
                "tagline":completion["tagline"],
                "mpaa_rating":completion["mpaa_rating"] if "mpaa_rating" in completion else "NR",
                "mpaa_rating_content":completion["rating_content"] if "rating_content" in completion else "NO RATING CONTENT",
                "critic_score":completion["critic_score"] if "critic_score" in completion else "NO CRITIC SCORE",
                "critic_review":completion["critic_review"] if "critic_review" in completion else "NO CRITIC REVIEW",
                "popularity_score":round(random.uniform(1, 10), 1),
                "genre":completion["genre"] if "genre" in completion else "NO GENRE",
                "description":completion["description"],
                "poster_url":"movie_poster_url.jpeg",
            }
        
        media_object["object_prompt"]=object_prompt
        media_object["object_prompt_list"]=object_prompt_list
        media_object["object_prompt_temperature"]=temperature
        media_object["azure_openai_text_completion_endpoint"]=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
        media_object["azure_openai_text_completion_deployment_name"]=deployment_name
        media_object["azure_openai_text_completion_api_version"]=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION")

        return json.dumps(media_object)
    else:
        outputMessage(f"Error generating object, missing important details (title, tagline or description) in completion.","error")
        return False
    
# Generate the prompt for the image based upon the media object info
def generateImagePrompt(media_object):
      
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

    # Send the description to the API
    try: 
        prompt_file = open(templates_base + "prompts.json", 'r')
    except IOError as e:
        outputMessage(f"Error opening {prompt_file}: {e}","error")
        exit()
    except Exception as e:
        outputMessage(f"An error occurred: {e}","error")
        return False

    prompt_json=json.load(prompt_file)
    prompt_file.close()
    prompt_image_json=random.choice(prompt_json["prompts_image"])

    #remove objects from media_object that are not needed for the promp
    object_keys_keep = ["title", "tagline", "mpaa_rating", "description"]
    media_object ={k: media_object[k] for k in object_keys_keep}
    media_object=json.dumps(media_object)
    full_prompt = prompt_image_json + json.dumps(media_object) + ",{'font_names':" + json.dumps(font_names)
    if args.verbose: outputMessage(f"Prompt\n {full_prompt}","verbose")
    
    # Create the AzureOpenAI client for image prompt
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT_KEY"),  
        api_version=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION"),
        azure_endpoint = os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    )
    deployment_name=os.getenv("AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME")

    try:
        response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":full_prompt}], max_tokens=500, temperature=0.7)
    except Exception as e:
        outputMessage(f"Error generating image prompt: {e}","error")
        if args.verbose: traceback.print_exc()
        return False
    
    completion=response.choices[0].message.content

    # Find the start and end index of the json object
    try:
        completion = json.loads(extractText(completion, "{", "}"))
        return completion
    except:
        outputMessage(f"Error parsing image prompt completion: {completion}","error")
        return False
    
# Generate the image using the prompt
def generateImage(image_completion, media_object):

    client = AzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_DALLE3_API_VERSION"),  
        api_key=os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT")
    )

    # Attempt to generate the image up to 5 times
    retries=5
    for _ in range(retries):
        try:
            result = client.images.generate(
                model=os.getenv("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME"), # the name of your DALL-E 3 deployment
                prompt=image_completion["image_prompt"],
                n=1,
                size="1024x1792"
            )
            break
        except Exception as e:
            outputMessage(f"Attempt {_+1} of {retries} failed to generate image for '{media_object['title']}'.","warning")
            if args.verbose: print(e)
            continue
    else:
        outputMessage(f"Error generating image for '{media_object['title']}' after {retries} attempts","error")
        return False

    # Grab the first image from the response
    json_response = json.loads(result.model_dump_json())

    # Retrieve the generated image and save it to the images directory
    image_url = json_response["data"][0]["url"]  # extract image URL from response
    generated_image = BytesIO(requests.get(image_url).content)  # download the image
    
    return generated_image

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

    except Exception as e:
        outputMessage(f"Error processing image: {e}","error")
        if args.verbose: traceback.print_exc()
        return False

    vision_completion = response.choices[0].message.content

    # Find the start and end index of the json object for the vision completion
    try:
        vision_completion = json.loads(extractText(vision_completion, "{", "}"))
    except:
        outputMessage(f"Error parsing vision prompt completion: {vision_completion}","error")
        return False

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
                y_placement = y_placements[y_location] + (font_height * (line_count - 1)) + (font_height * .70) 
            font_color = vision_completion["font_color"] if "font_color" in vision_completion else "#000000"
            stroke_color = "#111111" if font_color > "#999999" else "#DDDDDD"
            # put the text on the image
            draw.text((w_placement, y_placement), text_line, fill=font_color, font=font, stroke_width=1, stroke_fill=stroke_color, align='center') 
            line_count += 1

        return img

# Creates a directory based upon the directory path provided
def createDirectory(directory):

    try:
        os.makedirs(directory, exist_ok=True)
    except:
        outputMessage(f"Error creating directory {directory}.","error")
        return False

    return True

def saveItem(item, type, item_id):

    item_path = getOutputPath(type, item_id, "jpg" if type == "images" else "json")
    folder_path = os.path.dirname(item_path) 
    result = createDirectory(folder_path)
    if result == True:
        try:
            if type == "images":
                item = item.convert('RGB').resize((724, 1267))
                item.save(item_path, 'JPEG', quality=75)
            elif type == "json":
                with open(item_path, "w") as json_file:
                    json.dump(item, json_file)
                    json_file.write("\n")
            return item_path
        except Exception as e:
            outputMessage(f"Error saving {type}.\n{e}","error")
            return False
    else:
        return False

# Main function to run the generator
def main():

    start_time=datetime.datetime.now()

    #global process_id 
    process_id = createProcessId()
    # Create a main_id to store the original process_id
    main_id = process_id

    # Check if a count command line value is provided and is a digit, if not default to 1
    generate_count=1
    if(args.count) and args.count.isdigit():
        generate_count=int(args.count)
    
    outputMessage(f"Starting creation of {str(generate_count)} media object{'s' if generate_count > 1 else ''}","")

    # Notify if dry run mode is enabled
    if(args.dryrun): outputMessage("Dry run mode enabled, generated media objects will not be saved","verbose")

    # Main loop to generate the media objects, including json and images
    i=0
    success_count=0
    while i < generate_count:
        
        object_start_time = datetime.datetime.now()

        process_id = createProcessId()
        # Print the current media count being generated
        outputMessage(f"Creating media object: {str(i+1)} of {str(generate_count)}","info")

        # Build the prompt and print it when verbose mode is enabled and successful
        outputMessage(f"Building object prompt","")
        object_prompt, object_prompt_list=generateObjectPrompt()
        if not object_prompt:
            continue
        if args.verbose: 
            outputMessage(f"Object prompt:\n {object_prompt}","verbose")
            outputMessage(f"Template list:\n {json.dumps(object_prompt_list, indent=4)}","verbose")
        outputMessage(f"Finished building prompt, build time: {str(datetime.datetime.now() - object_start_time)}","")

        # Submit the object prompt for completion and print the object completion when verbose mode is enabled and successful
        outputMessage(f"Submitting object prompt for completion","")
        media_object=json.loads(generateObject(object_prompt, object_prompt_list))
        if not media_object:
            continue
        if args.verbose:
            outputMessage(f"Object completion:\n {json.dumps(media_object, indent=4)}","verbose") # Print the completion
        outputMessage(f"Finished generating media object '{media_object['title']}', object generate time: {str(datetime.datetime.now() - object_start_time)}","")

        ### Image creation ###
        image_start_time = datetime.datetime.now()
        outputMessage(f"Creating image for '{media_object['title']}'","")

        # Generate the image prompt and print it when verbose mode is enabled and successful
        outputMessage(f"Generating image prompt for '{media_object['title']}'","") 
        image_completion=generateImagePrompt(media_object)
        if not image_completion:
            continue
        if args.verbose: 
            outputMessage(f"Image prompt:\n{image_completion['image_prompt']}","verbose")
        outputMessage(f"Image prompt generated for '{media_object['title']}', image prompt generate time: {str(datetime.datetime.now() - image_start_time)}","")


        # Generate the image and if successful, add text to the image and save it as well as media object
        outputMessage(f"Generating image for '{media_object['title']}' from prompt","")
        generated_image = generateImage(image_completion, media_object)
        if generated_image:
            # Add text to image
            image = processImage(generated_image, image_completion, media_object)
            if not image:
                outputMessage(f"Error processing image for '{media_object['title']}'","error")
                continue
            else:
                outputMessage(f"Image created for '{media_object['title']}', image generate time: {str(datetime.datetime.now() - image_start_time)}","")
                media_object["image_generation_time"] = str(datetime.datetime.now())
                media_object["image_prompt"] = image_completion["image_prompt"].replace("'", "\"")
                media_object["image_font"] = image_completion["font"] if "font" in image_completion else "arial"
                media_object["azure_openai_image_model_endpoint"] = os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT")
                media_object["azure_openai_image_model_deployment"] = os.getenv("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME")
                media_object["azure_openai_image_model_api_version"] = os.getenv("AZURE_OPENAI_DALLE3_API_VERSION")
                media_object["create_time"]=str(datetime.datetime.now())
                
                # Save the media object and image to the outputs directory
                item_path = saveItem(media_object, "json", media_object["id"]) # Save Media JSON
                if item_path: # Json saved successfully, save image
                    image_path = saveItem(image, "images", media_object["id"]) # Save Poster Image
                    if image_path: # Image saved successfully
                        outputMessage(f"Media created: '{media_object['title']}', generate time: {str(datetime.datetime.now() - object_start_time)}","success")
                        success_count+=1
                    else: # Image failed to save, deleting media object
                        outputMessage(f"Error saving image for '{media_object['title']}', cleaning up media json created","success")
                        os.remove(item_path)
        i+=1
    process_id = main_id
    outputMessage(f"Finished generating {str(success_count)} media object{'s' if success_count > 1 else ''} of {generate_count}, Total Time: {str(datetime.datetime.now() - start_time)}","success")

process_id = ""
load_dotenv()
#Basic environment variable check before execution of anything
envCheck("AZURE_OPENAI_COMPLETION_ENDPOINT_KEY")
envCheck("AZURE_OPENAI_COMPLETION_API_VERSION")
envCheck("AZURE_OPENAI_COMPLETION_ENDPOINT")
envCheck("AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME")
envCheck("AZURE_OPENAI_DALLE3_ENDPOINT_KEY")
envCheck("AZURE_OPENAI_DALLE3_API_VERSION")
envCheck("AZURE_OPENAI_DALLE3_ENDPOINT")
envCheck("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME")
envCheck("AZURE_OPENAI_GPT4_VISION_ENDPOINT")
envCheck("AZURE_OPENAI_GPT4_VISION_ENDPOINT_KEY")
envCheck("AZURE_OPENAI_GPT4_VISION_DEPLOYMENT_NAME")
envCheck("AZURE_OPENAI_GPT4_VISION_API_VERSION")

working_dir=os.getcwd()
templates_base=working_dir + "/library-management/templates/"
outputs_dir="outputs/media/generated/"

# For command line arguments
parser = argparse.ArgumentParser(description="Provide various run commands.")
# Argument for the count of media objects to generate
parser.add_argument("-c", "--count", help="Number of media objects to generate")
# Argument for the dry run, to generate a response without saving it to a file TODO, actually make this do something
parser.add_argument("-d", "--dryrun", action='store_true', help="Dry run, generate a response without saving it to a file")
# Argument for verbose mode, to display object outputs
parser.add_argument("-v", "--verbose", action='store_true', help="Show details of steps and outputs like prompts and completions")
args = parser.parse_args()

if __name__ == "__main__":
    main()