import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import random
import hashlib
import sys
import argparse
import datetime


# REQUIREMENTS
# pip install python-dotenv
# pip install openai

# TODO - Add proper error handling for failed requests, try/except blocks

# Simply grabs a random value from the template file provided
def getTemplateValue(template):
    with open(templates_base + template + ".json") as json_file:
        return random.choice(json.load(json_file)[template])

# Parses the prompt template and replaces the values with the random values from the template file
def parseTemplate(template, prompt_list):

    start_index = template.find("{")
    while start_index != -1:
        end_index = template.find("}")
        text = template[start_index+1:end_index]
        replace_value=getTemplateValue(text)
        template = template.replace("{"+text+"}", replace_value,1)
        if text not in prompt_list:
            prompt_list[text] = []
        prompt_list[text].append(replace_value)
        start_index = template.find("{")
    return template, prompt_list

# Builds the prompt from the prompt template selected
def buildPrompt():

    prompt_list={}
    with open(templates_base + "prompts.json") as json_file:

        # Load the prompt template file and parse the prompt template
        prompt_json=json.load(json_file)
        prompt_start, prompt_list=parseTemplate(random.choice(prompt_json["prompts_start"]), prompt_list)
        prompt_cast, prompt_list=parseTemplate(random.choice(prompt_json["prompts_cast"]), prompt_list)
        prompt_synopsis, prompt_list=parseTemplate(random.choice(prompt_json["prompts_synopsis"]), prompt_list)
        prompt_end, prompt_list=parseTemplate(random.choice(prompt_json["prompts_end"]), prompt_list)
        prompt=f"{prompt_start} {prompt_cast} {prompt_synopsis} {prompt_end}"

        return prompt, prompt_list

# Submits the prompt to the API and returns the response as a formatted json object
def submitPrompt(prompt, prompt_list):

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
    
    media_object["prompt"]=prompt
    media_object["prompt_list"]=prompt_list
    media_object["azure_openai_text_completion_endpoint"]=os.getenv("AZURE_OPENAI_COMPLETION_ENDPOINT")
    media_object["azure_openai_text_completion_deployment_name"]=deployment_name
    media_object["azure_openai_text_completion_api_version"]=os.getenv("AZURE_OPENAI_COMPLETION_API_VERSION")

    return json.dumps(media_object)

# Saves the media object to a file based upon ID hash 
def saveCompletion(media_object):

    now = datetime.datetime.now()
    base_dir=os.path.join(os.getcwd(),outputs_dir)
    date_depth="%Y/%m/%d"#/%H/%M/%S"

    # Format the date and time
    folder_path = os.path.join(base_dir, now.strftime(date_depth))
    # Create the folders
    try:
        os.makedirs(folder_path, exist_ok=True)
    except:
        print(f"Error creating date folders for media object {media_object['id']}.")
        return False

    file_path = os.path.join(base_dir, now.strftime(date_depth), f"{media_object["id"]}.json")
    
    try:
        with open(file_path, "w") as json_file:
            json.dump(media_object, json_file)
            json_file.write("\n")
            return True
    except Exception as e:
        print(f"Error saving media object {media_object['id']}.\n{e}")
        return False


# Main function to run the generator
def main():

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

        # Print the current media count being generated
        print(f"{str(datetime.datetime.now())} - Generating media object: {str(i+1)} of {str(generate_count)}")

        # Build the prompt and print it
        if args.verbose: print(f"{str(datetime.datetime.now())} - Building Prompt")
        prompt, prompt_list=buildPrompt()
        if args.verbose: 
            print(f"{str(datetime.datetime.now())} - Finished Building Prompt")
            print(f"PROMPT:\n {prompt}")
            print(f"TEMPLATE LIST:\n {json.dumps(prompt_list, indent=4)}")

        # Submit the prompt for completion and print the completion
        if args.verbose: print(f"{str(datetime.datetime.now())} - Submitting Prompt for Completion")
        completion=json.loads(submitPrompt(prompt, prompt_list))
        if args.verbose:
            print(f"{str(datetime.datetime.now())} - Completion Received")
            print("COMPLETION:\n" + json.dumps(completion, indent=4)) # Print the completion

        # Save the media object if dry run mode is not enabled
        if not args.dryrun:
            if args.verbose: print(f"{str(datetime.datetime.now())} - Saving {completion["title"]}, {completion["id"]}")
            saveCompletion(completion)
            print(f"{str(datetime.datetime.now())} - SAVED - {completion["title"]}, {completion["id"]}")

        i+=1

    print(f"{str(datetime.datetime.now())} - Finsished generating {str(generate_count)} media object(s)")

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