import ollama

import os
import requests
import json
import time
import random

from io import BytesIO

# Parent class for the Azure OpenAI models
class ollamaModel():

    def __init__(self):
        self.model = ""
        self.system_prompt = ""
        self.user_prompt = ""
    
    def to_json(self):
        # Return a clean json object for saving details without sensitive information
        return {
            "model": self.model
        }

# Child class for the Azure OpenAI Text model
class ollamaText(ollamaModel):
    def __init__(self):
        super().__init__()
        self.model = os.getenv("LOCAL_MODEL_NAME")

    def generateResponse(self):
        response = ollama.chat(
            model=self.model, 
            messages=[
                { "role": "system", "content": self.system_prompt},
                {"role": "user", "content":self.user_prompt}
            ],
        )
        
        return response.message.content

# Child class for the Azure OpenAI Image model
# We are doing ComfyUI/StableDiffusion here, but I am too lazy to name the class better
class ollamaImage(ollamaModel):
    def __init__(self):
        super().__init__()
        self.model = os.getenv("AZURE_OPENAI_IMAGE_MODEL")

    def generateImage(self):
        full_prompt = json.loads(
"""
{"prompt": 
  {
  "3": {
    "inputs": {
      "seed": 189699095330452,
      "steps": 30,
      "cfg": 5.45,
      "sampler_name": "euler",
      "scheduler": "sgm_uniform",
      "denoise": 1,
      "model": [
        "4",
        0
      ],
      "positive": [
        "16",
        0
      ],
      "negative": [
        "40",
        0
      ],
      "latent_image": [
        "53",
        0
      ]
    },
    "class_type": "KSampler",
    "_meta": {
      "title": "KSampler"
    }
  },
  "4": {
    "inputs": {
      "ckpt_name": "stableDiffusion3SD3_sd3MediumInclClips.safetensors"
    },
    "class_type": "CheckpointLoaderSimple",
    "_meta": {
      "title": "Load Checkpoint"
    }
  },
  "8": {
    "inputs": {
      "samples": [
        "3",
        0
      ],
      "vae": [
        "4",
        2
      ]
    },
    "class_type": "VAEDecode",
    "_meta": {
      "title": "VAE Decode"
    }
  },
  "9": {
    "inputs": {
      "filename_prefix": "ComfyUI",
      "images": [
        "8",
        0
      ]
    },
    "class_type": "SaveImage",
    "_meta": {
      "title": "Save Image"
    }
  },
  "16": {
    "inputs": {
      "text": "A guy named Nick who dances in Texas with the words 'I love Texas' written in a classic script above him",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "Positive Prompt"
    }
  },
  "40": {
    "inputs": {
      "text": "disfigured, deformed, ugly, beginner",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "Negative Prompt"
    }
  },
  "53": {
    "inputs": {
      "width": 768,
      "height": 1344,
      "batch_size": 1
    },
    "class_type": "EmptySD3LatentImage",
    "_meta": {
      "title": "EmptySD3LatentImage"
    }
  }
}
}
"""
        )
        try:
            full_prompt["prompt"]["16"]["inputs"]["text"] = self.user_prompt
            full_prompt["prompt"]["3"]["inputs"]["seed"] = random.randint(10**14, 10**15)
            response = requests.post(
                "http://172.23.112.1:8188/prompt",
                headers={
                    "Content-Type": "application/json"
                },
                data=json.dumps(full_prompt)
            )

            initial_gen_response = response.json()

            status = "running"
            filename = ""
            while status != "success":
                time.sleep(.5)
                history_response = requests.get(
                    f"http://172.23.112.1:8188/history/{initial_gen_response['prompt_id']}"
                )
                if history_response.json() != {}:
                    status = history_response.json()[initial_gen_response['prompt_id']]["status"]["status_str"]
                    if status == "success":
                        filename = history_response.json()[initial_gen_response['prompt_id']]["outputs"]["9"]["images"][0]["filename"]
                        break
                    elif status == "error":
                        raise Exception("Error generating image")
                time.sleep(5)
            
            return BytesIO(requests.get(f"http://172.23.112.1:8188/view?filename={filename}").content)
        except Exception as e:
            raise
        
        


# Child class for the Azure OpenAI Vision model
class ollamaVision(ollamaModel):
    def __init__(self):
        super().__init__()
        self.model = "llama3.2-vision" #os.getenv("LOCAL_MODEL_NAME")
        self.image_base64 = ""

    def generateResponse(self):
        response = ollama.chat(
            model=self.model, 
            messages=[
                { "role": "system", "content": self.system_prompt},
                {"role": "user", "content":self.user_prompt, "images": [self.image_base64] }
            ],
        )
        
        return response.message.content