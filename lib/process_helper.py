import logging
import json
import os
import datetime
import hashlib
import random

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

        fileHandler = logging.FileHandler("{0}/{1}.log".format('outputs', 'movie_generation'))
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