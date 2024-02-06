import os
#from openai import AzureOpenAI
import json
import random

# TODO Rewrite all to take API call variable or be passed in.
default_count=5
try:
    default_count
except NameError:
    generate_count=1 #Default to only one generation if no amount is passed
else:
    if isinstance(default_count, int):
        generate_count=default_count
    else:
        exit("No valid count provided")

working_dir=os.getcwd()
templates_base=working_dir + "/library-management/templates/"

def getTemplateValue(template):
    with open(templates_base + template + ".json") as json_file:
        return random.choice(json.load(json_file)[template])

def parseTemplate(template):
    start_index = template.find("{")
    while start_index != -1:
        end_index = template.find("}")
        text = template[start_index+1:end_index]
        template = template.replace("{"+text+"}", getTemplateValue(text),1)
        start_index = template.find("{")
    return template

def buildPrompt():
    with open(templates_base + "prompts.json") as json_file:
        prompt_json=json.load(json_file)
        prompt=prompt_json["prompt_start"] + " " + parseTemplate(random.choice(prompt_json["prompts"])) + " " + prompt_json["prompt_end"]
        return prompt

def getCompletion(prompt):
    print("hello")
    

i=0
while i < generate_count:
    print(buildPrompt())
    i+=1

# print(os.getcwd())
# print(os.path.dirname(os.path.realpath(__file__)))
# client = AzureOpenAI(
#     api_key=os.getenv("AZURE_OPENAI_KEY"),  
#     api_version="2023-12-01-preview",
#     azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
#     )

