import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import random
import hashlib
import sys
import argparse

# REQUIREMENTS
# pip install python-dotenv
# pip install openai

# TODO
# 1. Checks for failures and move forward. If a failure occurs, log the prompt and response to a file for review

class MediaObject:
    def __init__(self, title, description, url):
        self.id = None
        self.title = None
        self.tagline = None
        self.rating = None
        self.rating_content = None
        self.critic_score = None
        self.critic_review = None
        self.popularity_score = None
        self.popularity_reason = None
        self.theme = None
        self.description = None
        self.prompt = None
        self.image_prompt = None
        self.poster_url = "movie_poster.jpg"
        self.cast = [
            {
                "role_one": None,
                "role_two": None,
                "director": None
            }
        ]
        self.aoai_deployment = None

    def to_json(self):
        return json.dumps(self.__dict__)

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

        # Load the prompt template file and parse the prompt template
        prompt_json=json.load(json_file)
        prompt_start=parseTemplate(random.choice(prompt_json["prompts_start"]))
        prompt_main=parseTemplate(random.choice(prompt_json["prompts_main"]))
        prompt_end=parseTemplate(random.choice(prompt_json["prompts_end"]))
        prompt=prompt_start + " " + prompt_main + " " + prompt_end
        return prompt

# Submits the prompt to the API and returns the response as a formatted json object
def submitPrompt(prompt):

    # Create the AzureOpenAI client
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT_KEY"),  
        api_version=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION"),
        azure_endpoint = os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    )
    deployment_name=os.getenv("AZURE_OPENAI_COMPLETION_DEPLOYMENT_NAME")
    
    # TODO: Add error handling for failed requests
    # Send the prompt to the API
    response = client.chat.completions.create(model=deployment_name, messages=[{"role": "user", "content":prompt}], max_tokens=500, temperature=0.7)

    # Parse the response and return the formatted json object
    completion=response.choices[0].message.content

    # Find the start and end index of the json object
    start_index = completion.find("{")
    end_index = completion.find("}")
    completion = json.loads(completion[start_index:end_index+1])

    # Create a hash ID for the media object based upon the title
    hash_object = hashlib.md5()
    hash_object.update(completion["title"].encode())
    media_id = hash_object.hexdigest()

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
            #"popularity_score":completion["popularity_score"],
            #"popularity_reason":completion["popularity_reason"],
            #"theme":completion["theme"],
            "description":completion["description"],
            "prompt":prompt,
            #"image_prompt":completion["image_prompt"],
            "poster_url":"movie_poster_url.jpeg",

            "aoai_deployment":deployment_name
        }
    
    return json.dumps(media_object)


# Saves the media object to a file based upon ID hash 
def saveCompletion(media_object):

    # TODO add error handling for failed file writes
    with open(working_dir + "/outputs/media/objects/"+media_object["id"]+".json", "a") as json_file:
        json.dump(media_object, json_file)
        json_file.write("\n")

# Main function to run the generator
def main():

    # For command line arguments
    parser = argparse.ArgumentParser(description="Provide various run commands.")
    # Argument for the count of media objects to generate
    parser.add_argument("-c", "--count", help="Number of media objects to generate")
    # Argument for the dry run, to generate a response without saving it to a file
    parser.add_argument("-d", "--dryrun", action='store_true', help="Dry run, generate a response without saving it to a file")
    parser.add_argument("-q", "--quiet", action='store_true', help="Hide object outputs like prompts and completions")

    args = parser.parse_args()

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
    if(args.quiet): print("\nQuiet mode enabled, no object outputs will be displayed, just steps info")

    # Main loop to generate the media objects
    i=0
    while i < generate_count:

        # Print the current media count being generated
        print("\nGenerating media object: " + str(i+1) + " of " + str(generate_count))

        # Build the prompt and print it        
        prompt=buildPrompt()
        if not args.quiet: print("\nPROMPT:\n" + prompt) # Print the prompt

        # Submit the prompt for completion and print the completion
        completion=json.loads(submitPrompt(prompt))
        if not args.quiet: print("\nCOMPLETION:\n" + json.dumps(completion, indent=4)) # Print the completion

        # Save the media object if dry run mode is not enabled
        if not args.dryrun:
            saveCompletion(completion)
            if not args.quiet: print("\nSAVED:" + completion["title"] + ", " + completion["id"]) # Print the saved object

        i+=1

    print("\nMedia objects generated: " + str(generate_count))

load_dotenv()
working_dir=os.getcwd()
templates_base=working_dir + "/library-management/templates/"

if __name__ == "__main__":
    main()