import random
import datetime
import json
import os
import traceback

from lib.process_helper import processHelper
from lib.aoai_model import aoaiText
from lib.ollama_model import ollamaText



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
        self.model_type = ""
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
        #self.aoai_text = aoaiText()
        #self.aoai_image = aoaiImage()
        #self.aoai_vision = aoaiVision()
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
            #"aoai_text": self.aoai_text.to_json(),
            #"aoai_image": self.aoai_image.to_json(),
            #"aoai_vision": self.aoai_vision.to_json(),
            "image_generation_time": self.image_generation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "prompts_temperature": self.prompts_temperature,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S")
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
        if self.model_type == "azure_openai":
            text_model = aoaiText()
        else:
            text_model = ollamaText()

        text_model.user_prompt = self.movie_prompt["movie"]
        text_model.system_prompt = self.movie_prompt["movie_system"]
      
        # Send the prompt to the API
        try:
            #self.movie_prompt["prompt_temperature"] = round(random.uniform(0.6,1.1),2) # Generate a random movie prompt temperature for funsies
            completion = text_model.generateResponse()
        except Exception as e:
            self._process.outputMessage(f"Error generating object : {e}", "error")
            if self._verbose: 
                self._process.outputMessage(traceback.format_exc(), "verbose")
            return False

        # Parse the response and return the formatted json object
        # Find the start and end index of the json object
        try:
            json_from_completion = self._process.extractJson(completion, "{", "}")
            
            # We need to check if the title, tagline and description exists in the completion, if not we cant use the completion for later purposes
            if "title" in json_from_completion and "tagline" in json_from_completion and "description" in json_from_completion:
                self.media_id = self._process.process_id
                self.title = json_from_completion["title"]
                self.tagline = json_from_completion["tagline"]
                self.mpaa_rating = json_from_completion["mpaa_rating"] if "mpaa_rating" in json_from_completion else "NR"
                self.mpaa_rating_content = json_from_completion["rating_content"] if "rating_content" in json_from_completion else "NO RATING CONTENT"
                self.genre = self.object_prompt_list["genres"][0] if "genres" in self.object_prompt_list else "NO GENRE"
                self.description = json_from_completion["description"]
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