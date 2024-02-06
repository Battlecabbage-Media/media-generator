import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import random

load_dotenv()

# TODO Rewrite all to take API call variable or be passed in.
default_count=1
try:
    default_count
except NameError:
    generate_count=1 #Default to only one generation if no amount is passed
else:
    if isinstance(default_count, int):
        generate_count=default_count
    else:
        exit("No valid count provided")

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


def submitPrompt(prompt):

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),  
        api_version="2023-12-01-preview",
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        )

    deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME") #This will correspond to the custom name you chose for your deployment when you deployed a model. Use a gpt-35-turbo-instruct deployment. 
    
    # Send a completion call to generate an answer
    print('Sending a movie plot completion job.\nPrompt:\n'+prompt+'\n')
    response = client.completions.create(model=deployment_name, prompt=prompt, max_tokens=500, temperature=0.6)
    print(response.choices[0].text)
    
i=0
while i < generate_count:
    prompt=buildPrompt()
    submitPrompt(prompt)
    i+=1


