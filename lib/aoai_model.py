from openai import AzureOpenAI
import os
import json
import requests
from io import BytesIO

# Parent class for the Azure OpenAI models
class aoaiModel():

    def __init__(self):
        self.endpoint = ""
        self.key = ""
        self.api_version = ""
        self.deployment_name = ""
        self.model = ""
        self.client = None
        self.system_prompt = ""
        self.user_prompt = ""
    
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

    def generateResponse(self):
        response = self.client.chat.completions.create(
            model=self.deployment_name, 
            messages=[
                { "role": "system", "content": self.system_prompt},
                {"role": "user", "content":self.user_prompt}
            ],
            max_tokens=600, temperature=self.prompts_temperature)
        
        return response.choices[0].message.content

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

    def generateImage(self):
                # Attempt to generate the image up to 5 times


        result = self.client.images.generate(
            model=self.deployment_name,
            prompt=self.user_prompt,
            n=1,
            size="1024x1792"
        )
                

        # Grab the first image from the response
        json_response = json.loads(result.model_dump_json())

        # Retrieve the generated image and save it to the images directory
        image_url = json_response["data"][0]["url"]  # extract image URL from response
        return BytesIO(requests.get(image_url).content)  # download the image

# Child class for the Azure OpenAI Vision model
class aoaiVision(aoaiModel):
    def __init__(self):
        super().__init__()
        self.endpoint = os.getenv("AZURE_OPENAI_VISION_ENDPOINT")
        self.key = os.getenv("AZURE_OPENAI_VISION_ENDPOINT_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_VISION_API_VERSION")
        self.deployment_name = os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT_NAME")
        self.model = os.getenv("AZURE_OPENAI_VISION_MODEL")
        self.image_base64 = ""
        self.mime_type = "image/png"

        self.client = AzureOpenAI(
            api_key=self.key,  
            api_version=self.api_version,
            azure_endpoint=self.endpoint
            #base_url=f"{self.endpoint}openai/deployments/{self.deployment_name}/extensions"
        )

    def generateResponse(self):
        response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    { "role": "system", "content": self.system_prompt },
                    { "role": "user", "content": [  
                        { 
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{self.mime_type};base64,{self.image_base64}"
                            }
                        },
                        { 
                            "type": "text", 
                            "text": self.user_prompt
                        }
                    ] } 
                ],
                max_tokens=2000 
            )
        return response.choices[0].message.content