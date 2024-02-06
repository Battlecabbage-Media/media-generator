import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import random
import hashlib
import sys

load_dotenv()

# Check if a count is provided, if not default to 1
default_count=1
if len(sys.argv) > 1: 
    if isinstance(sys.argv[1], int):
        generate_count=sys.argv[1]
else:
    generate_count=default_count

# TODO how does this work for a function?
working_dir=os.getcwd()
templates_base=working_dir + "/library-management/templates/"

# Simply grabs a random value from the template file provided
def getTemplateValue(template):
    with open(templates_base + template + ".json") as json_file:
        return random.choice(json.load(json_file)[template])

# Parses the prompt template and replaces the values with the random values from the template file
def parseTemplate(template):
    start_index = template.find("{")
    while start_index != -1:
        end_index = template.find("}")
        text = template[start_index+1:end_index]
        template = template.replace("{"+text+"}", getTemplateValue(text),1)
        start_index = template.find("{")
    return template

# Builds the prompt from the prompt template selected
def buildPrompt():
    with open(templates_base + "prompts.json") as json_file:
        prompt_json=json.load(json_file)
        prompt_start=parseTemplate(random.choice(prompt_json["prompts_start"]))
        prompt_main=parseTemplate(random.choice(prompt_json["prompts_main"]))
        prompt_end=parseTemplate(random.choice(prompt_json["prompts_end"]))
        prompt=prompt_start + " " + prompt_main + " " + prompt_end
        return prompt

# Submits the prompt to the API and returns the response as a formatted json object
def submitPrompt(prompt):

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),  
        api_version=os.getenv("API_VERSION"),
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME")
    
    # Send a completion call to generate an answer
    print('Generating movie plot.\n\nPrompt:\n'+prompt+'\n')
    response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":prompt}], max_tokens=500, temperature=0.6)
    #print(response.choices[0].message.content)
    completion=response.choices[0].message.content
    start_index = completion.find("{")
    end_index = completion.find("}")
    completion = json.loads(completion[start_index:end_index+1])
    print(completion)

    # Create a new md5 hash object
    hash_object = hashlib.md5()
    # Update the hash object with the bytes of the string
    hash_object.update(completion["title"].encode())
    # Get the hexadecimal representation of the hash
    media_id = hash_object.hexdigest()

    media_object = { 
            "id":media_id,
            "title":completion["title"],
            "tagline":completion["tagline"],
            "rating":completion["rating"],
            "rating_content":completion["rating_content"],
            "description":completion["description"],
            "prompt":prompt,
            "image_prompt":completion["image_prompt"],
            "poster_url":"movie_poster_url.jpeg",
            "aoai_deployment":deployment_name
        }
    return json.dumps(media_object)

# Saves the media object to a file based upon ID hash 
def saveCompletion(media_object):

    with open(working_dir + "/outputs/media/"+media_object["id"]+".json", "a") as json_file:
        json.dump(media_object, json_file)
        json_file.write("\n")
        print("\nMedia object saved: " + media_object["id"])

# Main loop to generate the media objects
i=0
while i < generate_count:
    prompt=buildPrompt()
    media_object=json.loads(submitPrompt(prompt))
    saveCompletion(media_object)
    i+=1

print("\nMedia objects generated: " + str(generate_count))