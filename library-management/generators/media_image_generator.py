from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import requests
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
import json
import random

# REQUIREMENTS
# pip install matplotlib
# pip install python-dotenv
# pip install openai
# pip install pillow

load_dotenv()

# TODO:
# 1. Implement prompt generation from movie plot templates
# 2. Implement the ability to generate a response without saving it to a file, dry run
# 3. Implement checks for failures and move forward. If a failure occurs, log the prompt and response to a file for review, potenitally retrying the prompt a few times before moving on.
# 4. Ability to break up text into multine and format it for the poster.
# 5. Ability to add a logo to the poster like the rating
# 6. Format the font to have better readability. Maybe on complimentary color, outlines, etc.
# 7. Proper checks if certain values came back from completion, example critic_score
# 8. Check for letterbox image and regenerate, Cameron?


# Check if the image has already been generated
def checkImage(images_directory,image_id):
    if os.path.isfile(images_directory + image_id + ".jpg"):
        return True
    else:
        return False


# Generate the prompt for the image based upon the media object info
def generateImagePrompt(media_object):
    
    # Create the AzureOpenAI client for image prompt
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT_KEY"),  
        api_version=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION"),
        azure_endpoint = os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    )
    deployment_name=os.getenv("AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME")
    
    # TODO: Add error handling for failed requests
    # Send the description to the API
    with open(templates_base + "prompts.json") as json_file:

        prompt_json=json.load(json_file)
        prompt_image_json=random.choice(prompt_json["prompts_image"])
        #TODO maybe write this more efficiently?
        full_prompt = prompt_image_json + "\ntitle: " + media_object["title"] + "\ntagline: " + media_object["tagline"] + "\nMPAA Rating: " + media_object["mpaa_rating"] + "\ndescription: " + media_object["description"]

        response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":full_prompt}], max_tokens=500, temperature=0.7)
        completion=response.choices[0].message.content
        # Find the start and end index of the json object
        start_index = completion.find("{")
        end_index = completion.find("}")
        completion = json.loads(completion[start_index:end_index+1])

        return completion
    

# Generate the image using the prompt
def generateImage(image_prompt, media_object):

    client = AzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_DALLE3_API_VERSION"),  
        api_key=os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_DALLE3_ENDPOINT")
    )

    result = client.images.generate(
        model=os.getenv("AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME"), # the name of your DALL-E 3 deployment
        prompt=image_prompt["image_prompt"] + " Image has no text",
        n=1,
        size='1024x1792'
    )

    json_response = json.loads(result.model_dump_json())

    # If the directory doesn't exist, create it
    if not os.path.isdir(images_directory):
        os.mkdir(images_directory)

    # Initialize the image path (note the filetype should be png)
    image_path = os.path.join(images_directory, media_object["id"] +'.png')

    # Retrieve the generated image and save it to the images directory
    image_url = json_response["data"][0]["url"]  # extract image URL from response
    generated_image = requests.get(image_url).content  # download the image
    with open(image_path, "wb") as image_file:
        image_file.write(generated_image)


# Add various text to the image and resize
def processImage(completion, media_object):

    image=images_directory + "/" + media_object["id"] + ".png"

    # Open an image file for manipulation
    with Image.open(image) as img:
        
        #https://stackoverflow.com/questions/4902198/pil-how-to-scale-text-size-in-relation-to-the-size-of-the-image
        W, H = img.size

        draw = ImageDraw.Draw(img)

        text = media_object["title"]
        # text = media_object["title"].replace(':','\n:')

        fontsize = 1  # starting font size

        # portion of image width you want text width to be
        img_fraction = 0.95

        # TODO use the font suggested by the completion?
        fonts = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')
        font_selected=random.choice(fonts)
        font = ImageFont.truetype(font_selected, fontsize)
      
        # font = ImageFont.truetype("arial.ttf", fontsize)
        #print(img_fraction*img.size[0],'space',font.getlength(text),'start size')
        while font.getlength(text) < img_fraction*img.size[0]:
            # iterate until the text size is just larger than the criteria
            fontsize += 1
            font = ImageFont.truetype(font_selected, fontsize)
            #print(fontsize,'new size',font.getlength(text),'new length')

        # optionally de-increment to be sure it is less than criteria
        fontsize -= 1
        font = ImageFont.truetype(font_selected, fontsize)
        
        w = font.getlength(text)
        #w = draw.textlength(text, font_size=fontsize)
        w_placement=(W-w)/2
        draw.text((w_placement, 50), text, font=font) # put the text on the image


        draw = ImageDraw.Draw(img)
        text = media_object["tagline"]
        fontsize = 1  # starting font size

        # portion of image width you want text width to be
        img_fraction = 0.75

        font = ImageFont.truetype("arial.ttf", fontsize)
        while font.getlength(text) < img_fraction*img.size[0]:
            # iterate until the text size is just larger than the criteria
            fontsize += 1
            font = ImageFont.truetype("arial.ttf", fontsize)

        # optionally de-increment to be sure it is less than criteria
        fontsize -= 3
        font = ImageFont.truetype("arial.ttf", fontsize)

        print('final tag line font size',fontsize)
        w = draw.textlength(text, font_size=fontsize)
        w_placement=(W-w)/2
        draw.text((w_placement, H - 150), text, font=font) # put the text on the image

        img = img.resize((724, 1267))
        img = img.convert('RGB')
        img.save(image.replace('png', 'jpg'), 'JPEG', quality=25)

    #Delete the original png file
    os.remove(image)


def formatText(text, type, img):
    print("here")


def main():

    # Find the first JSON file (media object)
    for filename in os.listdir(objects_directory):
        if filename.endswith('.json'):
            filepath = os.path.join(objects_directory, filename)
            with open(filepath, 'r') as file:
                media_object = json.load(file)

                # Check if the image has already been generated or exists based upon id
                result = checkImage(images_directory, media_object["id"])
                if result == True:        

                    print("\nImage already exists for " + media_object["id"] + ", skipping.")

                elif result == False:

                    print("\nGenerating Image Prompt for "  + media_object["title"] + ", ID: " + media_object["id"])
                    completion=generateImagePrompt(media_object)
                    print("Image Prompt:\n" + completion["image_prompt"])
                    
                    generateImage(completion, media_object)
                    print("Image Generated for " + media_object["title"] + " at " + str(images_directory) + media_object["id"] + ".png")
                          
                    processImage(completion, media_object)

                continue

    else:
        print("\nNo Media Objects needing a poster generated.")
        exit()


load_dotenv()
working_dir=os.getcwd()
objects_directory = working_dir + "/outputs/media/objects/"
images_directory = working_dir + "/outputs/media/images/"
templates_base = working_dir + "/library-management/templates/"

# Run the main loop
main()