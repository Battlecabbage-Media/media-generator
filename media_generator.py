import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
import random
import hashlib
import argparse
import datetime
import logging
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

# NOTES
# This thing has gotten really hacky and needs to be cleaned up. I'm not happy with the way the classes are being used and the way the functions are being called.
# It started out very procedural because thats how I write, cabattag came in and added classes and I've been trying to make it work with the new classes and design
# but I made it worse. There is a lot that could be improved, lots of repeated logic/methods and just general messiness because it being such hybrid of procedural
# and OOP

# Custom format class to handle coloring of console output
class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - [%(levelname)s] - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Create a class for common values and functions across the script
class processHelper:
    
    def __init__(self):
        self.process_id = 0
        self.generate_count = 1
        self.generated_count = 0
        self.success_count = 0
        self.image_fail_count = 0
        self.completion_fail_count = 0
        self.save_fail_count = 0

        logFormatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s")
        self.rootLogger = logging.getLogger()

        fileHandler = logging.FileHandler("{0}/{1}.log".format('outputs', 'movie_generation.log'))
        fileHandler.setFormatter(logFormatter)
        self.rootLogger.addHandler(fileHandler)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(CustomFormatter())
        self.rootLogger.addHandler(consoleHandler)

        self.rootLogger.setLevel(logging.INFO)

    def createProcessId(self):
        self.process_id = hashlib.md5(str(random.random()).encode()).hexdigest()[:16]
    
    def envCheck(self, env_var):
        if os.getenv(env_var) is None:
            self.outputMessage(f"Environment variable {env_var} not set. Check '.example.env' for details.","error")
            exit(1)

    def outputMessage(self, message, level):
    
        if level == "error":
            self.rootLogger.error(f"{self.process_id} - {message}")
            #color = "\033[91m" # Red
        elif level == "success":
            self.rootLogger.info(f"{self.process_id} - {message}")
            color = "\033[92m" # Green
            print(f"{str(datetime.datetime.now())} - {self.process_id} - {color}{message}")
            print("\033[0m", end="") # Reset color
        elif level == "info":
            self.rootLogger.info(f"{self.process_id} - {message}")
            #color = "\033[94m" # Blue
        elif level == "warning":
            self.rootLogger.warning(f"{self.process_id} - {message}")
            #color = "\033[93m"  # Yellow
        elif level == "debug":
            self.rootLogger.debug(f"{self.process_id} - {message}")
            #color = "\033[95m"  # Purple
        elif level == "verbose":
            self.rootLogger.debug(f"{self.process_id} - {message}")
            #color = "\033[96m"  # Cyan
        else:
            self.rootLogger.info(f"{self.process_id} - {message}")
            #color = "\033[0m" # white

        #print(f"{str(datetime.datetime.now())} - {self.process_id} - {color}{message}")
        #print("\033[0m", end="") # Reset color

    # increments the generated count to keep loop going, is there a better way to do this?
    def incrementGenerateCount(self):
        self.generated_count += 1

    # Creates a directory based upon the directory path provided
    def createDirectory(self, directory):

        try:
            os.makedirs(directory, exist_ok=True)
        except:
            self.outputMessage(f"Error creating directory {directory}.","error")
            return False

        return True

    # Builds the output path for the media object based upon the type and id
    def getOutputPath(self, type, ext):
        now = datetime.datetime.now()
        base_dir=os.path.join(os.getcwd(),"outputs")
        date_depth="%Y/%m/%d"#/%H/%M/%S"

        file_path = os.path.join(base_dir, now.strftime(date_depth),type, f"{self.process_id}.{ext}")

        return file_path

    # Extracts text from a string based upon the start and end values
    def extractText(self, text, start, end):
        start_index = text.find(start)
        end_index = text.find(end)        
        return text[start_index:end_index+1]

    def extractJson(self, text, start, end):
        start_index = text.find(start)
        end_index = text.find(end)
        text = text[start_index:end_index+1]
        try:
            completion_json = json.loads(text)
        except:         
            # Escape the json string and return it
            completion_json = json.loads(text.replace("'", "\\'").replace("\n", "\\n"))
            self.outputMessage(f"Issue loading json, had to do some escaping:\n{completion_json}.","warning")

        return completion_json

# Parent class for the Azure OpenAI models
class aoaiModel():

    def __init__(self):
        self.endpoint = ""
        self.key = ""
        self.api_version = ""
        self.deployment_name = ""
        self.model = ""
        self.client = None
    
    def to_json(self):
        # Return a clean json object for saving details without sensitive information
        return {
            "endpoint": self.endpoint,
            "api_version": self.api_version,
            "deployment_name": self.deployment_name,
            "model": self.model
        }

# Child class for the Azure OpenAI Text model
class aoaiText(aoaiModel):
    def __init__(self):
        super().__init__()
        self.endpoint = os.getenv("AZURE_OPENAI_TEXT_ENDPOINT")
        self.key = os.getenv("AZURE_OPENAI_TEXT_ENDPOINT_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_TEXT_API_VERSION")
        self.deployment_name = os.getenv("AZURE_OPENAI_TEXT_DEPLOYMENT_NAME")
        self.model = os.getenv("AZURE_OPENAI_TEXT_MODEL")

        self.client = AzureOpenAI(
            api_key=self.key,  
            api_version=self.api_version,
            azure_endpoint=self.endpoint
        )

# Child class for the Azure OpenAI Image model
class aoaiImage(aoaiModel):
    def __init__(self):
        super().__init__()
        self.endpoint = os.getenv("AZURE_OPENAI_IMAGE_ENDPOINT")
        self.key = os.getenv("AZURE_OPENAI_IMAGE_ENDPOINT_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_IMAGE_API_VERSION")
        self.deployment_name = os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT_NAME")
        self.model = os.getenv("AZURE_OPENAI_IMAGE_MODEL")

        self.client = AzureOpenAI(
            api_key=self.key,  
            api_version=self.api_version,
            azure_endpoint=self.endpoint
        )

# Child class for the Azure OpenAI Vision model
class aoaiVision(aoaiModel):
    def __init__(self):
        super().__init__()
        self.endpoint = os.getenv("AZURE_OPENAI_VISION_ENDPOINT")
        self.key = os.getenv("AZURE_OPENAI_VISION_ENDPOINT_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_VISION_API_VERSION")
        self.deployment_name = os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT_NAME")
        self.model = os.getenv("AZURE_OPENAI_VISION_MODEL")

        self.client = AzureOpenAI(
            api_key=self.key,  
            api_version=self.api_version,
            azure_endpoint=self.endpoint
            #base_url=f"{self.endpoint}openai/deployments/{self.deployment_name}/extensions"
        )

# Class for the media object
class media:   
    def __init__(self, process: processHelper, prompt_file_path, templates_base, verbose=False):
        self.media_id = 0
        self.title = ""
        self.tagline = ""
        self.mpaa_rating = ""
        self.description = ""
        self.popularity_score = round(random.uniform(1, 10), 1)
        self.genre = ""
        self.reviews = []
        self.movie_prompt = {}
        self.image_prompt = {}
        self.vision_prompt = {
            "vision": "",
            "vision_system": "",
            "location": "top",
            "location_padding": 50,
            "font_color": "#FFFFFF",
            "has_text": False
        }
        self.object_prompt_list = {}
        # Setting some Models stuff
        self.aoai_text = aoaiText()
        self.aoai_image = aoaiImage()
        self.aoai_vision = aoaiVision()
        self.image_generation_time = datetime.datetime.now()
        self.prompts_temperature = round(random.uniform(0.6,1.1),2)
        self.create_time = datetime.datetime.now()

        # Anything with underscore will be ignored during serialization
        # Actually it won't be "ignored", I just won't add it to the "to_json" method...
        self._process = process
        self._prompt_file_path = prompt_file_path
        self._templates_base = templates_base
        self._verbose = verbose
        self._object_path = ""

    def to_json(self):
        return {
            "media_id": self.media_id,
            "title": self.title,
            "tagline": self.tagline,
            "mpaa_rating": self.mpaa_rating,
            "description": self.description,
            "popularity_score": self.popularity_score,
            "genre": self.genre,
            "reviews": self.reviews,
            "movie_prompt": self.movie_prompt,
            "image_prompt": self.image_prompt,
            "vision_prompt": self.vision_prompt,
            "prompt_value_list": self.object_prompt_list,
            "aoai_text": self.aoai_text.to_json(),
            "aoai_image": self.aoai_image.to_json(),
            "aoai_vision": self.aoai_vision.to_json(),
            "image_generation_time": self.image_generation_time,
            "prompts_temperature": self.prompts_temperature,
            "create_time": self.create_time
        }

    # Simply grabs a random value from the template file provided
    def getTemplateValue(self, template):
        try:
            template_path = os.path.join(self._templates_base, f"{template}.json")
            with open(template_path) as json_file:
                return random.choice(json.load(json_file)[template])
        except IOError as e:
            self._process.outputMessage(f"Error opening template file {template_path}: {e}", "error")
            exit()
        except Exception as e:
            self._process.outputMessage(f"An error occurred for {template_path}: {e}", "error")
            return False

    # Parses the prompt template and replaces the values with the random values from the template file
    def parseTemplate(self, template):
        start_index = template.find("{")
        while start_index != -1:
            end_index = template.find("}")
            text = template[start_index+1:end_index]
            replace_value=self.getTemplateValue(text)
            template = template.replace("{"+text+"}", replace_value,1)
            if text not in self.object_prompt_list:
                self.object_prompt_list[text] = []
            self.object_prompt_list[text].append(replace_value)
            start_index = template.find("{")
        return template
    
    # Builds the prompt from the prompt template selected
    def generateObjectPrompt(self):
        prompt_file_path = self._prompt_file_path
        try:
            with open(prompt_file_path) as prompt_file:
                prompts_json=json.load(prompt_file)

            self.movie_prompt["movie_system"] = self.parseTemplate(random.choice(prompts_json["movie_system"]))
            self.movie_prompt["movie"]=self.parseTemplate(random.choice(prompts_json["movie"]))
            return True
        except IOError as e:
            self._process.outputMessage(f"Error opening prompt file. {prompt_file_path}. Check that it exists!", "error")
            exit()
        except Exception as e:
            self._process.outputMessage(f"An issue occurred building the object prompt: {e}", "error")
            return False, "An error occurred."
        except:
            self._process.outputMessage(f"Error opening prompt file. {prompt_file_path}. Check that it exists!","error")
            exit(1)

    # Submits the prompt to the API and returns the response as a formatted json object
    def generateObject(self):

        # Create a text model object
        text_model = aoaiText()
      
        # Send the prompt to the API
        try:
            #self.movie_prompt["prompt_temperature"] = round(random.uniform(0.6,1.1),2) # Generate a random movie prompt temperature for funsies
            response = text_model.client.chat.completions.create(
                model=text_model.deployment_name, 
                messages=[
                    { "role": "system", "content": self.movie_prompt["movie_system"]},
                    {"role": "user", "content":self.movie_prompt["movie"]}
                ],
                max_tokens=600, temperature=self.prompts_temperature)
        except Exception as e:
            self._process.outputMessage(f"Error generating object : {e}", "error")
            if self._verbose: 
                self._process.outputMessage(traceback.format_exc(), "verbose")
            return False

        # Parse the response and return the formatted json object
        completion=response.choices[0].message.content

        # Find the start and end index of the json object
        try:
            completion = self._process.extractJson(completion, "{", "}")
            
            # We need to check if the title, tagline and description exists in the completion, if not we cant use the completion for later purposes
            if "title" in completion and "tagline" in completion and "description" in completion:
                self.media_id = self._process.process_id
                self.title = completion["title"]
                self.tagline = completion["tagline"]
                self.mpaa_rating = completion["mpaa_rating"] if "mpaa_rating" in completion else "NR"
                self.mpaa_rating_content = completion["rating_content"] if "rating_content" in completion else "NO RATING CONTENT"
                self.genre = self.object_prompt_list["genres"][0] if "genres" in self.object_prompt_list else "NO GENRE"
                self.description = completion["description"]
                self.poster_url = "movie_poster_url.jpeg"
                return True
            else:
                self._process.outputMessage(f"Error generating object, missing important details (title, tagline or description) in completion.","error")
                return False
        except Exception as e:
            self._process.outputMessage(f"Error parsing object completion","error")
            self._process.outputMessage(completion,"info")
            self._process.outputMessage(e,"error")
            return False

    # Save the media object to a json file
    def saveMediaObject(self):
        object_path = self._process.getOutputPath("json", "json")
        object_dir = os.path.dirname(object_path) 
        if self._process.createDirectory(object_dir):
            try:
                with open(object_path, "w") as json_file:
                    json.dump(self.to_json(), json_file)
                    json_file.write("\n")
                self._object_path = object_path
                return True
            except Exception as e:
                self._process.outputMessage(f"Error saving {type}.\n{e}","error")
                return False
        else:
            return False
    
    def objectCleanup(self):
        # Clean up the object by removing the json file, mainly if the image fails to save to avoid orphaned files.
        try:
            os.remove(self._object_path)
        except:
            self._process.outputMessage(f"Error removing object file {self._object_path}.","error")
            return False
        return True

# Class for a critic review
class criticReview:
    def __init__(self, media_object: media, verbose=False):
        self.media_object = media_object
        self.system_prompt = ""
        self.prompt = ""
        self.review = ""
        self.score = 0
        self.tone = ""

    # Generate the prompt for the critic review based upon the media object info
    def buildCriticPrompt(self):
        prompt_file_path = self.media_object._prompt_file_path
        process = self.media_object._process
        verbose = self.media_object._verbose
        try:
            with open(prompt_file_path) as prompt_file:
                prompt_json=json.load(prompt_file)
        except IOError as e:
            process.outputMessage(f"Error opening prompt file. {prompt_file_path}. Check that it exists!", "error")
            exit()
        except Exception as e:
            process.outputMessage(f"An issue occurred building the object prompt: {e}", "error")
            return False, "An error occurred."

        self.system_prompt = random.choice(prompt_json["critic_system"])
        critic_prompt_json=random.choice(prompt_json["critic"])
        start_index = critic_prompt_json.find("{")
        while start_index != -1:
            end_index = critic_prompt_json.find("}")
            key = critic_prompt_json[start_index+1:end_index]
            key_value = ""
            try:
                key_value = self.media_object.object_prompt_list[key][0] if key in self.media_object.object_prompt_list else self.media_object.__dict__[key]
            except:
                key_value = "NO VALUE"
            critic_prompt_json = critic_prompt_json.replace("{"+key+"}", key_value,1)
            start_index = critic_prompt_json.find("{")
        
        self.prompt=critic_prompt_json
        return True

    # Generate the critic review using the prompt
    def generateCriticReview(self):
        process = self.media_object._process
        verbose = self.media_object._verbose
        text_model = aoaiText()
      
        # Send the prompt to the API
        try:
            response = text_model.client.chat.completions.create(
                model=text_model.deployment_name, 
                messages=[
                    { "role": "system", "content":  self.system_prompt},
                    {"role": "user", "content":self.prompt}
                ],
                max_tokens=600, temperature=self.media_object.prompts_temperature)
        except Exception as e:
            process.outputMessage(f"Error generating critic review : {e}", "error")
            if verbose: 
                self._process.outputMessage(traceback.format_exc(), "verbose")
            return False
        
        # Parse the response
        completion=response.choices[0].message.content

        # Find the start and end index of the json object
        try:

            completion = process.extractJson(completion, "{", "}")

            if completion["critic_score"] and completion["critic_review"]:
                self.review = completion["critic_review"]
                self.score = completion["critic_score"]
                self.tone = completion["critic_tone"]
                return True
            else:
                process.outputMessage(f"Error generating critic review, missing important details (score or review) in completion.","error")
                return False
            
        except Exception as e:
            process.outputMessage(f"Error parsing review completion","error")
            process.outputMessage(completion,"info")
            process.outputMessage(e,"error")
            traceback.print_exc()
            return False
        
    def to_json(self):
        return {
            "system_prompt": self.system_prompt,
            "prompt": self.prompt,
            "review": self.review,
            "score": self.score,
            "tone": self.tone
        }

# Class for the image object
class image:
    def __init__(self, media_object: media):
        self.media_object = media_object
        self.poster_prompt = {}
        self.generated_image = 0
        self.completed_poster = 0

    # Generate the prompt for the image based upon the media object info
    def generateImagePrompt(self):
        prompt_file_path = self.media_object._prompt_file_path
        process = self.media_object._process
        verbose = self.media_object._verbose
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
            prompt_file = open(prompt_file_path, 'r')
        except IOError as e:
            process.outputMessage(f"Error opening {prompt_file}: {e}","error")
            exit()
        except Exception as e:
            process.outputMessage(f"An error occurred: {e}","error")
            return False

        with open(prompt_file_path) as prompt_file:
            prompt_json=json.load(prompt_file)

        # Get system prompt for generating image prompt completion    
        self.media_object.image_prompt["image_prompt_system"] = random.choice(prompt_json["image_prompt_system"])

        prompt_image_json=random.choice(prompt_json["image_prompt"])
        #remove objects from media_object that are not needed for the prompt
        object_prompt_list=self.media_object.object_prompt_list
        object_keys_keep = ["title", "tagline", "description"]
        pruned_media_object = {k: v for k, v in self.media_object.__dict__.items() if k in object_keys_keep}

        # Take a string and anywhere there is a {} replace it with the value from object_prompt_list or media_object, whatever has it
        # TODO we do this logic multiple times so likely a better way to do this
        start_index = prompt_image_json.find("{")
        while start_index != -1:
            end_index = prompt_image_json.find("}")
            key = prompt_image_json[start_index+1:end_index]
            key_value = ""
            try:
                key_value = object_prompt_list[key][0] if key in object_prompt_list else pruned_media_object[key]
            except:
                key_value = "NO VALUE"
            prompt_image_json = prompt_image_json.replace("{"+key+"}", key_value,1)
            start_index = prompt_image_json.find("{")

        self.media_object.image_prompt["image_prompt"] = prompt_image_json + "\nFonts:" + json.dumps(font_names)

        if verbose: process.outputMessage(f"Prompt\n {self.media_object.image_prompt}","verbose")

        text_model = aoaiText()
        try:

            response = text_model.client.chat.completions.create(
                model=text_model.deployment_name, 
                messages=[
                    { "role": "system", "content": self.media_object.image_prompt["image_prompt_system"]},
                    {"role": "user", "content":self.media_object.image_prompt["image_prompt"]}
                ],
                max_tokens=500, temperature=self.media_object.prompts_temperature)
            
        except Exception as e:
            process.outputMessage(f"Error generating image prompt: {e}","error")
            if verbose: 
                process.outputMessage(traceback.format_exc(), "verbose")
            return False
        
        completion=response.choices[0].message.content
        # Find the start and end index of the json object
        try:
            completion = process.extractJson(completion, "{", "}")
            self.media_object.image_prompt["image_prompt_completion"] = completion["image_prompt"]
            self.media_object.image_prompt["font"] = completion["font"]
            return True
        except Exception as e:
            process.outputMessage(f"Error parsing image prompt completion","error")
            process.outputMessage(completion,"info")
            process.outputMessage(e,"error")
            return False
        
    # Generate the image using the prompt
    def generateImage(self):
        process = self.media_object._process
        verbose = self.media_object._verbose
        
        image_model = aoaiImage()

        # Attempt to generate the image up to 5 times
        retries=5
        for _ in range(retries):
            try:
                result = image_model.client.images.generate(
                    model=image_model.deployment_name,
                    prompt=self.media_object.image_prompt["image_prompt_completion"],
                    n=1,
                    size="1024x1792"
                )
                break
            except Exception as e:
                process.outputMessage(f"Attempt {_+1} of {retries} failed to generate image for '{self.media_object.title}'\n{e}.","warning")
                continue
        else:
            process.outputMessage(f"Error generating image for '{self.media_object.title}' after {retries} attempts","error")
            return False

        # Grab the first image from the response
        json_response = json.loads(result.model_dump_json())

        # Retrieve the generated image and save it to the images directory
        image_url = json_response["data"][0]["url"]  # extract image URL from response
        self.generated_image = BytesIO(requests.get(image_url).content)  # download the image
        
        return True

    # Add text to the image and resize
    def processImage(self):
        prompt_file_path = self.media_object._prompt_file_path
        process = self.media_object._process
        verbose = self.media_object._verbose
        # Get a list of all font files
        font_files = font_manager.findSystemFonts(fontpaths=None, fontext='ttf')

        # The name of the font you're looking for
        font_name_to_find = self.media_object.image_prompt["font"]
        
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
        with open(prompt_file_path) as json_file:
            prompt_json=json.load(json_file)
        
        # Making this less dynamic to keep myself sane
        prompt = random.choice(prompt_json["vision"])
        prompt = prompt.replace("{title}", self.media_object.title)
        prompt = prompt.replace("{font}", self.media_object.image_prompt["font"] if self.media_object.image_prompt["font"] != "" else font_path.replace(".ttf", ""))
        self.media_object.vision_prompt["vision"] = prompt
        self.media_object.vision_prompt["vision_system"] = random.choice(prompt_json["vision_system"])
  
        mime_type = "image/png"
        base64_encoded_data = base64.b64encode(self.generated_image.read()).decode('utf-8')

        vision_model = aoaiVision()
        try:

            response = vision_model.client.chat.completions.create(
                model=vision_model.deployment_name,
                messages=[
                    { "role": "system", "content": self.media_object.vision_prompt['vision_system'] },
                    { "role": "user", "content": [  
                        { 
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_encoded_data}"
                            }
                        },
                        { 
                            "type": "text", 
                            "text": self.media_object.vision_prompt['vision']
                        }
                    ] } 
                ],
                max_tokens=2000 
            )

        except Exception as e:
            process.outputMessage(f"Error processing image: {e}","error")
            if verbose: 
                process.outputMessage(traceback.format_exc(), "verbose")
            return False

        vision_completion = response.choices[0].message.content
        # Find the start and end index of the json object for the vision completion
        try:
            vision_completion = process.extractJson(vision_completion, "{", "}")
        except Exception as e:
            process.outputMessage(f"Error parsing vision prompt completion","error")
            if verbose:
                process.outputMessage(vision_completion,"verbose")
                process.outputMessage(e,"verbose")
            return False
        
        if "location" in vision_completion:
            self.media_object.vision_prompt["location"] = vision_completion["location"]
        if "location_padding" in vision_completion:
            self.media_object.vision_prompt["location_padding"] = vision_completion["location_padding"]
        if "font_color" in vision_completion:
            self.media_object.vision_prompt["font_color"] = vision_completion["font_color"]
        if "has_text" in vision_completion:
            self.media_object.vision_prompt["has_text"] = vision_completion["has_text"]

        # Open the image file for manipulation
        with Image.open(self.generated_image) as img:

            draw = ImageDraw.Draw(img)
            
            # Check if the poster has text and if it doesnt, title it.
            if self.media_object.vision_prompt["has_text"] == False:

                img_w, img_h = img.size
                fontsize = 1  # starting font size
                font = ImageFont.truetype(font_path, fontsize)
                # Find font size to fit the text based upon fraction of the image width and biggest string section
                scale=.85

                text_string = self.media_object.title

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
                section_top =  self.media_object.vision_prompt["location_padding"]
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
                    y_location = self.media_object.vision_prompt["location"]
                    if line_count == 1:
                        y_placement = y_placements[y_location]
                    else:
                        y_placement = y_placements[y_location] + (font_height * (line_count - 1)) + (font_height * .70) 
                    font_color = self.media_object.vision_prompt["font_color"]
                    stroke_color = "#111111" if font_color > "#999999" else "#DDDDDD"
                    # put the text on the image
                    draw.text((w_placement, y_placement), text_line, fill=font_color, font=font, stroke_width=1, stroke_fill=stroke_color, align='center') 
                    line_count += 1

        self.completed_poster = img
        return True
    
    # Save the image to the images directory
    def saveImage(self):
        process = self.media_object._process
        image_path = process.getOutputPath("images", "jpg")
        image_dir = os.path.dirname(image_path) 
        if process.createDirectory(image_dir):
            try:
                self.completed_poster.save(image_path, 'JPEG', quality=75)
                return image_path
            except Exception as e:
                process.outputMessage(f"Error saving image: {e}","error")
                return False
        else:
            return False

# Main function to run the generator
def main():

    process = processHelper()

    # Load the environment variables from the .env file
    load_dotenv()

    process.envCheck("AZURE_OPENAI_TEXT_ENDPOINT_KEY")
    process.envCheck("AZURE_OPENAI_TEXT_API_VERSION")
    process.envCheck("AZURE_OPENAI_TEXT_ENDPOINT")
    process.envCheck("AZURE_OPENAI_TEXT_DEPLOYMENT_NAME")
    process.envCheck("AZURE_OPENAI_IMAGE_ENDPOINT_KEY")
    process.envCheck("AZURE_OPENAI_IMAGE_API_VERSION")
    process.envCheck("AZURE_OPENAI_IMAGE_ENDPOINT")
    process.envCheck("AZURE_OPENAI_IMAGE_DEPLOYMENT_NAME")
    process.envCheck("AZURE_OPENAI_VISION_ENDPOINT")
    process.envCheck("AZURE_OPENAI_VISION_ENDPOINT_KEY")
    process.envCheck("AZURE_OPENAI_VISION_DEPLOYMENT_NAME")
    process.envCheck("AZURE_OPENAI_VISION_API_VERSION")

    working_dir=os.getcwd()
    templates_base=os.path.join(working_dir, "templates")
    prompt_file_path = os.path.join(templates_base, "prompts.json") # Used in many locations so defined here
    # Check if the prompt file exists
    if not os.path.exists(prompt_file_path):
        process.outputMessage(f"Error opening prompt file and its really important. {prompt_file_path}. Check that it exists in templates!","error")
        exit(1)

    # For command line arguments
    parser = argparse.ArgumentParser(description="Provide various run commands.")
    # Argument for the count of media objects to generate
    # Add env as default to allow setting via env var
    parser.add_argument("-c", "--count", default=os.environ.get('GENERATE_COUNT'), help="Number of media objects to generate")
    # Argument for the dry run, to generate a response without saving it to a file TODO, actually make this do something
    parser.add_argument("-d", "--dryrun", action='store_true', help="Dry run, generate a response without saving it to a file")
    # Argument for verbose mode, to display object outputs
    parser.add_argument("-v", "--verbose", action='store_true', help="Show details of steps and outputs like prompts and completions")
    args = parser.parse_args()

    start_time=datetime.datetime.now()

    process.createProcessId()
    
    # Check if a count command line value is provided and is a digit, if not default to 1
    if(args.count) and args.count.isdigit():
        process.generate_count=int(args.count)
    
    process.outputMessage(f"Starting creation of {str(process.generate_count)} media object{'s' if process.generate_count > 1 else ''}","")

    # Notify if dry run mode is enabled
    if(args.dryrun): process.outputMessage("Dry run mode enabled, generated media objects will not be saved","verbose")

    # Main loop to generate the media objects, including json and images
    while process.generated_count < process.generate_count:
        
        object_start_time = datetime.datetime.now()

        process.createProcessId()

        # Print the current media count being generated
        process.outputMessage(f"Creating media object: {str(process.generated_count+1)} of {str(process.generate_count)}","info")
        media_object=media(process, prompt_file_path, templates_base, args.verbose)
        # Build the prompt and print it when verbose mode is enabled and successful
        process.outputMessage(f"Building object prompt","")
        if not media_object.generateObjectPrompt():
            process.incrementGenerateCount()
            continue
        if args.verbose: 
            process.outputMessage(f"Object prompt:\n {media_object.movie_prompt}","verbose")
            process.outputMessage(f"Template list:\n {json.dumps(media_object.object_prompt_list, indent=4)}","verbose")
        process.outputMessage(f"Finished building prompt, build time: {str(datetime.datetime.now() - object_start_time)}","")

        # Submit the object prompt for completion and print the object completion when verbose mode is enabled and successful
        process.outputMessage(f"Submitting object prompt for completion","")
        if not media_object.generateObject():
            process.incrementGenerateCount()
            process.completion_fail_count += 1
            continue
        else:
            if args.verbose:
                process.outputMessage(f"Object completion:\n {json.dumps(media_object, indent=4)}","verbose") # Print the completion
            process.outputMessage(f"Finished generating media object '{media_object.title}', object generate time: {str(datetime.datetime.now() - object_start_time)}","")

        #Creating a critic review for the movie
        process.outputMessage(f"Creating critic review for '{media_object.title}'","")
        review = criticReview(media_object, args.verbose)
        if not review.buildCriticPrompt():
            process.incrementGenerateCount()
            continue
        if args.verbose:
            process.outputMessage(f"Critic prompt:\n {review.prompt}","verbose")
        if not review.generateCriticReview():
            process.incrementGenerateCount()
            process.completion_fail_count += 1
            continue
        if args.verbose:        
            process.outputMessage(f"Critic review:\n {media_object.reviews}","verbose")
        media_object.reviews.append(review.to_json())
        process.outputMessage(f"Critic review created for '{media_object.title}', critic review generate time: {str(datetime.datetime.now() - object_start_time)}","")
    

        ### Image creation ###
        image_start_time = datetime.datetime.now()
        process.outputMessage(f"Creating image for '{media_object.title}'","")
        image_object = image(media_object)
        # Generate the image prompt and print it when verbose mode is enabled and successful
        process.outputMessage(f"Generating image prompt for '{media_object.title}'","") 
        
        if not image_object.generateImagePrompt():
            process.incrementGenerateCount()
            process.completion_fail_count += 1
            continue
        if args.verbose: 
            process.outputMessage(f"Image prompt:\n{image_object.poster_prompt['image_prompt']}","verbose")
        process.outputMessage(f"Image prompt generated for '{media_object.title}', image prompt generate time: {str(datetime.datetime.now() - image_start_time)}","")

        # Generate the image and if successful, add text to the image and save it as well as media object
        process.outputMessage(f"Generating image for '{media_object.title}' from prompt","")
        if image_object.generateImage():
            # Add text to image
            if not image_object.processImage():
                process.outputMessage(f"Error processing image for '{media_object.title}'","error")
                process.incrementGenerateCount()
                process.image_fail_count += 1
                continue
            else:
                process.outputMessage(f"Image created for '{media_object.title}', image generate time: {str(datetime.datetime.now() - image_start_time)}","")
                media_object.image_generation_time = str(datetime.datetime.now())
                media_object.create_time=str(datetime.datetime.now())
                
                # Save the media object and image to the outputs directory
                if media_object.saveMediaObject(): # Json saved successfully
                    # Save Poster Image
                    if image_object.saveImage(): # Image saved successfully
                        process.outputMessage(f"Media created: '{media_object.title}', generate time: {str(datetime.datetime.now() - object_start_time)}","success")
                        process.success_count += 1
                    else: # Image failed to save, deleting media object
                        process.outputMessage(f"Error saving image for '{media_object.title}', cleaning up media json created","error")
                        media_object.objectCleanup()
                        process.save_fail_count += 1
                else: # Json failed to save
                    process.outputMessage(f"Error saving media object '{media_object.title}', image not saved","error")
                    media_object.objectCleanup()
                    process.incrementGenerateCount()
                    process.save_fail_count += 1
                    continue
        else:
            process.image_fail_count += 1

        process.incrementGenerateCount()
    
    message_level = "success" if process.success_count == process.generate_count else "warning"
    process.outputMessage(f"Finished generating {str(process.success_count)} media object{'s' if process.success_count > 1 else ''} of {process.generate_count}, Total Time: {str(datetime.datetime.now() - start_time)}",message_level)
    if process.success_count < process.generate_count:
        process.outputMessage(f"Prompt Completion failures: {process.completion_fail_count}\nImage Generate Failures: {process.image_fail_count}\nSave Failures: {process.save_fail_count}","info")

if __name__ == "__main__":
    main()
