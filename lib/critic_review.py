import json
import random
import traceback

import lib.media as media
from lib.aoai_model import aoaiText
from lib.ollama_model import ollamaText


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

        # Create a text model object
        if self.media_object.model_type == "azure_openai":
            text_model = aoaiText()
        else:
            text_model = ollamaText()

        text_model.user_prompt = self.prompt
        text_model.system_prompt = self.system_prompt
      
        # Send the prompt to the API
        try:
            #self.movie_prompt["prompt_temperature"] = round(random.uniform(0.6,1.1),2) # Generate a random movie prompt temperature for funsies
            completion = text_model.generateResponse()
        except Exception as e:
            self._process.outputMessage(f"Error generating object : {e}", "error")
            if self._verbose: 
                self._process.outputMessage(traceback.format_exc(), "verbose")
            return False

        # Find the start and end index of the json object
        try:

            json_from_completion = process.extractJson(completion, "{", "}")

            if json_from_completion["critic_score"] and json_from_completion["critic_review"]:
                self.review = json_from_completion["critic_review"]
                self.score = json_from_completion["critic_score"]
                self.tone = json_from_completion["critic_tone"]
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
