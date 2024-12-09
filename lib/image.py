from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
from fontTools.ttLib import TTFont, TTCollection
import requests
from io import BytesIO
import base64
import traceback
import json
import os
import random

import lib.media as media
from lib.aoai_model import aoaiText, aoaiImage, aoaiVision
from lib.ollama_model import ollamaText, ollamaImage, ollamaVision

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

        # Create a text model object
        if self.media_object.model_type == "azure_openai":
            text_model = aoaiText()
        else:
            text_model = ollamaText()
        
        text_model.user_prompt = self.media_object.image_prompt["image_prompt"]
        text_model.system_prompt = self.media_object.image_prompt["image_prompt_system"]

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
            self.media_object.image_prompt["image_prompt_completion"] = json_from_completion["image_prompt"]
            self.media_object.image_prompt["font"] = json_from_completion["font"]
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

        if self.media_object.model_type == "azure_openai":
            image_model = aoaiImage()
        else:
            image_model = ollamaImage()

        image_model.user_prompt = self.media_object.image_prompt["image_prompt_completion"]

        retries=5
        for _ in range(retries):
            try:
                self.generated_image = image_model.generateImage()
                break
            except Exception as e:
                process.outputMessage(f"Attempt {_+1} of {retries} failed to generate image for '{self.media_object.title}'\n{e}.","warning")
                continue
        else:
            process.outputMessage(f"Error generating image for '{self.media_object.title}' after {retries} attempts","error")
            return False
        
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

        if self.media_object.model_type == "azure_openai":
            vision_model = aoaiVision()
        else:
            vision_model = ollamaVision()

        vision_model.image_base64 = base64_encoded_data
        vision_model.mime_type = mime_type
        vision_model.user_prompt = self.media_object.vision_prompt["vision"]
        vision_model.system_prompt = self.media_object.vision_prompt["vision_system"]
        try:

            vision_completion = vision_model.generateResponse()

        except Exception as e:
            process.outputMessage(f"Error processing image: {e}","error")
            if verbose: 
                process.outputMessage(traceback.format_exc(), "verbose")
            return False
        # Find the start and end index of the json object for the vision completion
        try:
            json_from_vision_completion = process.extractJson(vision_completion, "{", "}")
        except Exception as e:
            process.outputMessage(f"Error parsing vision prompt completion","error")
            if verbose:
                process.outputMessage(vision_completion,"verbose")
                process.outputMessage(e,"verbose")
            return False
        
        if "location" in json_from_vision_completion:
            self.media_object.vision_prompt["location"] = json_from_vision_completion["location"]
        if "location_padding" in json_from_vision_completion:
            self.media_object.vision_prompt["location_padding"] = json_from_vision_completion["location_padding"]
        if "font_color" in json_from_vision_completion:
            self.media_object.vision_prompt["font_color"] = json_from_vision_completion["font_color"]
        if "has_text" in json_from_vision_completion:
            self.media_object.vision_prompt["has_text"] = json_from_vision_completion["has_text"]

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
