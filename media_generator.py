import os
from dotenv import load_dotenv
import json
import argparse
import datetime

from lib.process_helper import processHelper
from lib.media import media
from lib.image import image
from lib.critic_review import criticReview

# REQUIREMENTS
# pip install python-dotenv
# pip install openai

# NOTES
# This thing has gotten really hacky and needs to be cleaned up. I'm not happy with the way the classes are being used and the way the functions are being called.
# It started out very procedural because thats how I write, cabattag came in and added classes and I've been trying to make it work with the new classes and design
# but I made it worse. There is a lot that could be improved, lots of repeated logic/methods and just general messiness because it being such hybrid of procedural
# and OOP

# Main function to run the generator
def main():

    process = processHelper()

    # Load the environment variables from the .env file
    load_dotenv()

    process.envCheck("MODEL_TYPE")
    if os.getenv("MODEL_TYPE").lower() != "azure_openai":
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
    elif os.getenv("MODEL_TYPE").lower() != "local":
        process.envCheck("LOCAL_MODEL_NAME")

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
                media_object.image_generation_time = datetime.datetime.now()
                media_object.create_time=datetime.datetime.now()
                
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
