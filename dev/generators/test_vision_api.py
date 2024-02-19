import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import argparse
import base64
from mimetypes import guess_type

# Purpose: Testing the Vision API for images to suggest title locations of movies
# There  are two flags to use with this script:
# -d or --dryrun: This will generate the prompt only without calling the API
# -s or --single: This will only process a single image

load_dotenv()

# Function to encode a local image into data URL 
def local_image_to_data_url(image_path):
    # Guess the MIME type of the image based on the file extension
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Default MIME type if none is found

    # Read and encode the image file
    with open(image_path, "rb") as image_file:
        base64_encoded_data = base64.b64encode(image_file.read()).decode('utf-8')

    # Construct the data URL
    #return mime_type, base64_encoded_data
    return f"data:{mime_type};base64,{base64_encoded_data}"

api_base = os.getenv("AZURE_OPENAI_GPT4_VISION_ENDPOINT") # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
api_key=os.getenv("AZURE_OPENAI_GPT4_VISION_ENDPOINT_KEY")
deployment_name = os.getenv("AZURE_OPENAI_GPT4_VISION_DEPLOYMENT_NAME")
api_version = os.getenv("AZURE_OPENAI_GPT4_VISION_API_VERSION") # this might change in the future


# For command line arguments
parser = argparse.ArgumentParser(description="Provide various run commands.")
# Argument for the dry run, to generate a response without saving it to a file
parser.add_argument("-d", "--dryrun", action='store_true', help="Generate prompt only without calling the API")
# Argument for verbose mode, to display object outputs
parser.add_argument("-s", "--single", action='store_true', help="Only process a single image")
args = parser.parse_args()



client = AzureOpenAI(
    api_key=api_key,  
    api_version=api_version,
    base_url=f"{api_base}openai/deployments/{deployment_name}/extensions",
)

# Loop through all images in directory
examples_base = os.getcwd() + "/dev/examples/"
images_base = examples_base + "images/"

count = 0
print(images_base)
for image in os.listdir(images_base):

    # Only process a single image
    if args.single and count > 0:
        break

    print(image)
    image_path = images_base + image
    data_url = local_image_to_data_url(image_path)
    # print("Data URL:", data_url)

    # Get matching media object for image
    media_object_path = examples_base + "media_objects/" + image.replace("image","media_object").replace(".png", ".json")
    with open(media_object_path, 'r') as file:
        media_object = json.load(file)

    if media_object.get('image_font') is None:
        continue

    prompt = f"Movie Title: '{media_object['title']}' \n Title Font: '{media_object['image_font']}'" 

    print("Prompt:", prompt)

    # Skip the API call if dry run mode is enabled
    if args.dryrun:
        continue

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            { "role": "system", "content": "You are an expert graphic designer who creates movie posters. You will be given a title, font, and image. Provide the best place to put the title as top, middle, or bottom in the property location. Provide the pixel padding required to fit the title best as an integer in the property location_padding. Provide the color the title should be to be the most visualy interesting from the list of Material Design colors, avoiding yellows (kittens get really sad when they see yellow) as a hex color value in the property font_color. Output this information in JSON form." },
            { "role": "user", "content": [  
                { 
                    "type": "text", 
                    "text": prompt 
                },
                { 
                    "type": "image_url",
                    "image_url": {
                        #"url": f"data:{mime_type};base64,{base64_encoded_data}"
                        "url": local_image_to_data_url(image_path)
                    }
                }
            ] } 
        ],
        max_tokens=2000 
    )
    print(response.choices[0].message.content)
    count += 1