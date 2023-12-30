from openai import OpenAI
import os
import discord
import pickle
import asyncio
import requests
from concurrent.futures import ThreadPoolExecutor
from Utils import constructHelpMsg, read_pdf, delete_file, debug_log
import time
from PIL import Image
import io, base64

class Dalle:
    def __init__(self, debug:bool):
        self.DEBUG = debug
        # openai.api_key = os.getenv("gpt_OPENAI_API_KEY")
        self.model = "dall-e-3"
        self.client = OpenAI()

    # TODO: there's also option to allow editing of images only with DALLE2 model
    # note however that inpatining/outpainting requires us manually generating a mask and using that mask to edit the image
        
    async def main(self, prompt : str) -> Image:
        '''
        Create an image using Dalle from openai and return it as a base64-encoded image
        '''
        def blocking_api_call():
            return self.client.images.generate(
                        model = self.model,
                        prompt = prompt,
                        size = "1024x1024",
                        quality = "standard",
                        response_format = "b64_json",
                        n = 1,
                    )

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, blocking_api_call)

        # decode from base 64 json into image
        encoded_img = response.data[0].b64_json
        image = Image.open(io.BytesIO(base64.b64decode(encoded_img)))

        # return image
        return image


class ChatGPT:
    def __init__(self, debug:bool):
        self.DEBUG = debug
        self.tmp_dir = "./tmp"

        self.client = OpenAI()
        self.gpt_channel_name = os.getenv('GPT_CHANNEL_NAME')
        self.gpt_model_to_max_tokens = {
            "gpt-4-1106-preview": [128000, "Apr 2023"], 
            "gpt-4-vision-preview" : [128000, "Apr 2023"], 
            "gpt-4" : [8192, "Sep 2021"]
        }
        self.gpt_settings = {
            "model": ["gpt-4-vision-preview", "str"], 
            "prompt": ["", "str"],
            "messages" : [[], "list of dicts"],
            "temperature": ["0.0", "float"],
            "top_p": ["1.0", "float"],
            "frequency_penalty": ["0", "float"],
            "presence_penalty": ["0", "float"],
            "max_tokens": [128000, "int"],
        }
        self.chatgpt_name="assistant"
        self.cmd_prefix = "!"

        # gpt prompts
        self.gpt_prompts_file = os.getenv("GPT_PROMPTS_FILE") # pickled prompt name -> prompts dict
        self.all_gpt_available_prompts = None # list of all prompt names
        self.map_promptname_to_prompt = None # dictionary of (k,v) = (prompt_name, prompt_as_str)
        self.curr_prompt_name = None  # name of prompt we're currently using

        # modifying prompts
        self.modify_prompts_state = None
        self.modify_prompts_state_tmp = None
        self.personal_assistant_modify_prompts_buff = []

        self.commands = {
            "help" : "display this message",
            "convo len" : 'show current gpt context length',
            "reset thread" : 'reset gpt context length',
            "show thread" : 'show the entire current convo context',
            "gptsettings" : 'show the current gpt settings',
            "gptset": "format is `gptset, [setting_name], [new_value]` modify gpt settings",
            "curr prompt": "get the current prompt name",
            "change prompt": "format is `change prompt, [new prompt]`, change prompt to the specified prompt(NOTE: resets entire message thread)",
            "show prompts": "show the available prompts for gpt",
            "models": "list the available gpt models",
            "modify prompts": "modify the prompts for gpt",
            "save thread": "save the current gptX thread to a file",
            "show old threads": "show the old threads that have been saved",
            "load thread": "format is `load thread, [unique id]` load a gptX thread from a file",
            "delete thread": "format is `delete thread, [unique id]` delete a gptX thread from a file",
            "current model": "show the current gpt model",
            "swap": "swap between different models",
        }
        self.commands_help_str = constructHelpMsg(self.commands)

        # initialize prompts
        self.gpt_read_prompts_from_file() # read the prompts from disk
        self.init_prompt_name = "empty" # NOTE: up to user, i like starting with an empty prompt
        self.gpt_context_reset(prompt_name=self.init_prompt_name)
    
    async def genGPTResponseNoAttachments(self, prompt : str, settings_dict : dict = None) -> str:
        '''
        retrieves a GPT response given a string input and a dictionary containing the settings to use
        returns the response str
        '''
        if settings_dict is None:
            settings_dict = self.gpt_settings

        # init content with the user's message
        content = [
            {"type": "text",
             "text": prompt
            }
        ]

        new_usr_msg = {
            "role": "user",
            "content": content
        }

        if self.DEBUG: debug_log(f"{new_usr_msg=}")

        ##############################
        # update list of messages, then use it to query
        settings_dict["messages"][0].append(new_usr_msg)

        def blocking_api_call():
            # query
            return self.client.chat.completions.create(
                model = settings_dict["model"][0],
                messages = settings_dict["messages"][0],
                temperature = float(settings_dict["temperature"][0]),
                top_p = float(settings_dict["top_p"][0]),
                frequency_penalty = float(settings_dict["frequency_penalty"][0]),
                presence_penalty = float(settings_dict["presence_penalty"][0]),
                max_tokens = 4096 # NOTE: this is hardcoded like this bc preview models are not ready for prod-level outputs yet
            )
        
        # Run the blocking function in a separate thread using run_in_executor
        if self.DEBUG: debug_log(f"Sent to ChatGPT API: {settings_dict['messages'][0]}")
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            completion = await loop.run_in_executor(executor, blocking_api_call)
        
        chatgptcompletion = completion.choices[0].message.content
        if self.DEBUG: debug_log(f"Got response from ChatGPT API: {chatgptcompletion}")
        return chatgptcompletion

    async def genGPTResponseWithAttachments(self, msg : discord.message.Message, settings_dict: dict = None) -> str:
        '''
        retrieves a GPT response given a string input and a dictionary containing the settings to use
        checks for attachments in the discord Message construct
        returns the response str
        '''
        if settings_dict is None:
            settings_dict = self.gpt_settings

        response_msg = ""

        # init content with the user's message
        content = [
            {"type": "text",
             "text": msg.content
            }
        ]

        # attachments 
        text_file_formats = ['.txt', '.c', '.cpp', '.py', '.java', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.md']
        image_file_formats = ['.jpg', '.png', '.heic']
        if msg.attachments:
            for attachment in msg.attachments:
                # text files (plain text and code)
                for file_format in text_file_formats:
                    if attachment.filename.endswith(file_format):
                        # Download the attachment
                        file_content = requests.get(attachment.url).text
                        # append to text data to be sent
                        content[0]['text'] = content[0]['text'] + "\nFILE CONTENTS:\n" + file_content

                # images (allow .jpg, .png, .heic)
                for image_format in image_file_formats:
                    if attachment.filename.endswith(image_format):
                        if settings_dict["model"][0] == "gpt-4-vision-preview":
                            image_dict = {"type": "image_url"}
                            image_dict["image_url"] = attachment.url
                            content.append(image_dict)
                        else:
                            response_msg += f"Discarded image (current model is not an image model): {attachment.filename}\n"
                
                # pdfs (grab embedded and ocr text -- use both in context)
                if attachment.filename.endswith('.pdf'):
                    response = requests.get(attachment.url) # download pdf
                    pdf_file = f"{self.tmp_dir}/tmp.pdf"
                    with open(pdf_file, "wb") as f:
                        f.write(response.content)
                    embedded_text, ocr_text = read_pdf(pdf_file)
                    delete_file(pdf_file)
                    content[0]['text'] = content[0]['text'] + "\nPDF CONTENTS:\n" + embedded_text + "\nOCR CONTENTS:\n" + ocr_text

        new_usr_msg = {
            "role": "user",
            "content": content
        }

        if self.DEBUG: debug_log(f"{new_usr_msg=}")

        ##############################
        # update list of messages, then use it to query
        settings_dict["messages"][0].append(new_usr_msg)

        def blocking_api_call():
            # query
            return self.client.chat.completions.create(
                model = settings_dict["model"][0],
                messages = settings_dict["messages"][0],
                temperature = float(settings_dict["temperature"][0]),
                top_p = float(settings_dict["top_p"][0]),
                frequency_penalty = float(settings_dict["frequency_penalty"][0]),
                presence_penalty = float(settings_dict["presence_penalty"][0]),
                max_tokens = 4096 # TODO: why is this hardcoded?
            )
        
        # Run the blocking function in a separate thread using run_in_executor
        if self.DEBUG: debug_log(f"Sent to ChatGPT API: {settings_dict['messages'][0]}")
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            completion = await loop.run_in_executor(executor, blocking_api_call)
        
        chatgptcompletion = completion.choices[0].message.content
        response_msg += chatgptcompletion
        if self.DEBUG: debug_log(f"Got response from ChatGPT API: {chatgptcompletion}")
        return response_msg

    async def mainNoAttachments(self, prompt : str) -> str:
        '''
        Alternative entrance function for only plain text inputs...
        '''
        # check to see if we are running out of tokens for current msg log
        # get the current thread length
        curr_thread = await self.get_curr_gpt_thread()
        curr_thread_len_in_tokens = len(curr_thread) / 4 # 1 token ~= 4 chars
        while curr_thread_len_in_tokens > int(self.gpt_settings["max_tokens"][0]):
            # remove the 2nd oldest message from the thread (first oldest is the prompt)
            self.gpt_settings["messages"][0].pop(1)
        
        # use usr_msg to generate new response from API
        gpt_response = await self.genGPTResponseNoAttachments(prompt)

        # reformat to put into messages list for future context, and save
        formatted_response = {"role":self.chatgpt_name, "content":gpt_response}
        self.gpt_settings["messages"][0].append(formatted_response)

        return gpt_response

    ################# Entrance #################
    async def main(self, msg : discord.message.Message) -> str:
        '''
        Entrance function for all ChatGPT API things.
        Either modifies the parameters or generates a response based off of current context and new user message.
        Returns the generation.
        '''
        usr_msg = str(msg.content)
        if len(usr_msg) > 0:
            # catch if is a command
            if usr_msg[0] == self.cmd_prefix:
                if len(usr_msg) == 1: return "Empty command provided."
                # pass to PA block without the prefix
                return await self.modifyParams(msg, usr_msg[1:])

        # check to see if we are running out of tokens for current msg log
        # get the current thread length
        curr_thread = await self.get_curr_gpt_thread()
        curr_thread_len_in_tokens = len(curr_thread) / 4 # 1 token ~= 4 chars
        while curr_thread_len_in_tokens > int(self.gpt_settings["max_tokens"][0]):
            # remove the 2nd oldest message from the thread (first oldest is the prompt)
            self.gpt_settings["messages"][0].pop(1)
        
        # use usr_msg to generate new response from API
        gpt_response = await self.genGPTResponseWithAttachments(msg)

        # reformat to put into messages list for future context, and save
        formatted_response = {"role":self.chatgpt_name, "content":gpt_response}
        self.gpt_settings["messages"][0].append(formatted_response)

        return gpt_response
        
    ################# Entrance #################

    def _setPrompt(self, prompt : str) -> None:
        '''
        set the prompt for the model and update the messages settings dict
        '''
        self.curr_prompt_str = prompt
        self.gpt_settings["prompt"][0] = prompt
        l = self.gpt_settings["messages"][0]
        if len(l) == 0:
            l.append([{'role':'assistant', 'content':prompt}])
        else:
            l[0] = {'role':'assistant', 'content':prompt}
        self.gpt_settings["messages"][0] = l

    async def _modify_prompts(self, usr_msg : str) -> str:
        '''
        handles changing the prompts for chatgpt
        returns any message needed to be sent to user
        '''
        # user can cancel at any time
        if usr_msg == "cancel":
            # cancel modifying any prompts
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            self.personal_assistant_modify_prompts_buff = []
            return "Ok, cancelling."

        # Stage 1: usr picks a operator
        if self.modify_prompts_state_tmp == "asked what to do":
            # check response
            if usr_msg == "edit":
                self.modify_prompts_state_tmp = "edit"
                return "Ok which prompt would you like to edit? [enter prompt name]"
            elif usr_msg == "add":
                self.modify_prompts_state_tmp = "add"
                return "Ok, write a prompt in this format: [name]<SEP>[PROMPT] w/o the square brackets."
            elif usr_msg == "delete":
                self.modify_prompts_state_tmp = "delete"
                return "Ok, which prompt would you like to delete? [enter prompt name]"
            elif usr_msg == "changename":
                self.modify_prompts_state_tmp = "changename"
                return "Ok, which prompt name would you like to rename? [enter prompt name]"
            else:
                return "Invalid response, please try again."

        # Stage 2: usr provides more info for an already chosen operator
        if self.modify_prompts_state_tmp == "edit":
            self.personal_assistant_modify_prompts_buff.append(usr_msg)
            self.modify_prompts_state_tmp = "edit2"
            return f"Ok, you said to edit {usr_msg}.\nSend me the new prompt for this prompt name. (just the new prompt in its entirety)"
        if self.modify_prompts_state_tmp == "edit2":
            # update our mapping of prompt name to prompt dict, then write the new prompts to file
            prompt_name = self.personal_assistant_modify_prompts_buff.pop()
            new_prompt = usr_msg
            self.map_promptname_to_prompt[prompt_name] = new_prompt
            self.gpt_save_prompts_to_file() # write the new prompts to file
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return f"Updated '{prompt_name}' to '{new_prompt}'"
        if self.modify_prompts_state_tmp == "add":
            prompt_name = usr_msg.split("<SEP>")[0]
            prompt = usr_msg.split("<SEP>")[1]
            self.map_promptname_to_prompt[prompt_name] = prompt
            self.gpt_save_prompts_to_file() # write the new prompts to file
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return f"Added '{prompt_name}' with prompt '{prompt}'"
        if self.modify_prompts_state_tmp == "delete":
            prompt_name = usr_msg
            del self.map_promptname_to_prompt[prompt_name]
            self.gpt_save_prompts_to_file() # write the new prompts to file
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return f"Deleted '{prompt_name}'"
        if self.modify_prompts_state_tmp == "changename":
            self.personal_assistant_modify_prompts_buff.append(usr_msg)
            self.modify_prompts_state_tmp = "changename2"
            return f"Ok, what would you like to change the {usr_msg} to?"
        if self.modify_prompts_state_tmp == "changename2":
            prompt_name = self.personal_assistant_modify_prompts_buff.pop()
            new_prompt_name = usr_msg
            prompt = self.map_promptname_to_prompt[prompt_name]
            del self.map_promptname_to_prompt[prompt_name]
            self.map_promptname_to_prompt[new_prompt_name] = prompt
            self.gpt_save_prompts_to_file() # write the new prompts to file
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return  f"Changed '{prompt_name}' to '{new_prompt_name}'"

    async def modifyParams(self, msg : discord.message.Message, usr_msg : str) -> str:
        '''
        Modifies ChatGPT API params.
        Returns the output of an executed command or returns an error/help message.
        '''
        # convert shortcut to full command if present
        usr_msg = self.shortcut_cmd_convertor(usr_msg)

        # if in middle of modifying prompts
        if self.modify_prompts_state is not None:
            return await self._modify_prompts(usr_msg)

        # help
        if usr_msg == "help": return self.commands_help_str

        # save current msg log to file 
        if usr_msg == "save thread":
            global time
            # pickle the current thread from gptsettings["messages"][0]
            msgs_to_save = self.gpt_settings["messages"][0]
            # grab current time in nanoseconds
            curr_time = time.time()
            # pickle the msgs_to_save and name it the current time
            with open(f"./pickled_threads/{curr_time}.pkl", "wb") as f:
                pickle.dump(msgs_to_save, f, protocol=pickle.HIGHEST_PROTOCOL)
            return f"Saved thread to file as {curr_time}.pkl"
 
        # show old threads that have been saved
        if usr_msg == "show old threads":
            ret_str = ""
            # for now, list all the threads...
            for filename in os.listdir("./pickled_threads"):
                # read the file and unpickle it
                with open(f"./pickled_threads/{filename}", "rb") as f:
                    msgs_to_load = pickle.load(f)
                    ret_str += f"Thread id: {filename[:-4]}\n" # hide the file extension when displayed, its ugly
                    for tmp in msgs_to_load:
                        tmp_role = tmp["role"]
                        tmp_msg = tmp["content"]
                        ret_str += f"###{tmp_role.capitalize()}###\n{tmp_msg}\n###################\n"
                    ret_str += f"{'~ '*30}"
            return ret_str

        # load msg log from file
        if usr_msg[:11] == "load thread":
            tmp = usr_msg.split(",")
            if len(tmp) != 2:
                return "No thread id specified. usage: [load thread, THREAD_ID]"

            thread_id = tmp[1].strip()

            if len(thread_id) == 0:
                return "No thread id specified"

            if thread_id[-4:] == ".pkl":
                thread_id = thread_id[:-4]

            # read the file and unpickle it
            with open(f"./pickled_threads/{thread_id}.pkl", "rb") as f:
                msgs_to_load = pickle.load(f)
                # set the current gptsettings messages to this 
                self.gpt_settings["messages"][0] = msgs_to_load
            return  f"Loaded thread {thread_id}.pkl"
        
        # delete a saved thread
        if usr_msg[:13] == "delete thread":
            thread_id = usr_msg.split(",")[1].strip()

            if len(thread_id) == 0:
                return "No thread id specified"

            # delete the file
            os.remove(f"./pickled_threads/{thread_id}.pkl")
            return f"Deleted thread {thread_id}.pkl"

        # list available models of interest
        if usr_msg == "models":
            tmp = "".join([f"{k}: {v}\n" for k,v in self.gpt_model_to_max_tokens.items()])
            ret_str = f"Available models:\n{tmp}" 
            if self.DEBUG: debug_log(f"!models\n {tmp}")
            return ret_str

        # show the current gpt prompt
        if usr_msg == "curr prompt":
            return self.curr_prompt_name

        # just show current model
        if usr_msg == "current model":
            return f"Current model: {self.gpt_settings['model'][0]}"
        
        # toggle which model to use (toggle between the latest gpt4 turbo and the vision model)
        if usr_msg == "swap":
            curr_model = self.gpt_settings["model"][0]
            if self.DEBUG: debug_log(f"swap: {curr_model=}")
            if curr_model == "gpt-4-vision-preview":
                await self.modifygptset(msg, "gptset model gpt-4-1106-preview")
            else:
                await self.modifygptset(msg, "gptset model gpt-4-vision-preview")
            return f'Set to: {self.gpt_settings["model"][0]}'

        # add a command to add a new prompt to the list of prompts and save to file
        if usr_msg == "modify prompts":
            if self.modify_prompts_state is None:
                self.modify_prompts_state = "modify prompts"
                self.modify_prompts_state_tmp = "asked what to do" 
                return f"These are the existing prompts:\n{self.get_all_gpt_prompts_as_str()}\nDo you want to edit an existing prompt, add a new prompt, delete a prompt, or change a prompt's name? (`edit` `add` `delete` `changename`)\nNote that you should preface inputs with the command prefix char. You can also stop this process with `cancel`"

        # change gpt prompt
        if usr_msg[:13] == "change prompt":
            # accept only the prompt name, update both str of msgs context and the messages list in gptsettings
            try:
                new_prompt_name = list(map(str.strip, usr_msg.split(',')))[1]
                if new_prompt_name not in self.all_gpt_available_prompts:
                    return f"Prompt {new_prompt_name} not available. Available prompts: {' '.join(self.all_gpt_available_prompts)}"
                self.gpt_context_reset(prompt_name=new_prompt_name)
                return "New current prompt set to: " + new_prompt_name
            except Exception as e:
                return "usage: change prompt, [new prompt]"

        # show available prompts as (ind. prompt)
        if usr_msg == "show prompts":
            return self.get_all_gpt_prompts_as_str()

        # show user current gpt settings
        if usr_msg == "gptsettings":
            return self.gptsettings()

        # user wants to modify gpt settings
        if usr_msg[0:6] == "gptset":
            await self.modifygptset(msg, usr_msg)
            return self.gptsettings()
        
        # show the current thread
        if usr_msg == "show thread":
            ret_str = ""
            for tmp in self.gpt_settings["messages"][0]:
                tmp_role = tmp["role"]
                tmp_msg = tmp["content"]
                ret_str += f"###{tmp_role.capitalize()}###\n{tmp_msg}\n###################\n"
            return ret_str

        # reset the current convo with the curr prompt context
        if usr_msg == "reset thread":
            self.gpt_context_reset()
            return f"Thread Reset. {await self.get_curr_convo_len_and_approx_tokens()}"
        
        # check curr convo context length
        if usr_msg == "convo len":
            return await self.get_curr_convo_len_and_approx_tokens()
        
        return "Unknown command."

    def shortcut_cmd_convertor(self, usr_msg :str) -> str:
        '''
        if the user enters a shortcut command, convert it to the actual command
        '''
        if usr_msg == "rt":
            return "reset thread"
        if usr_msg == "cl":
            return "convo len"
        if usr_msg == "st": 
            return "show thread"
        if usr_msg[:2] == "cp":
            return "change prompt" + usr_msg[1:]
        if usr_msg == "save":
            return "save thread"
        if usr_msg[:4] == "load" and usr_msg[5:11] != "thread":
            return "load thread" + usr_msg[3:]
        if usr_msg == "cm":
            return "current model"

        # not a shortcut command
        return usr_msg

    # convo len
    async def get_curr_convo_len_and_approx_tokens(self) -> str:
        '''
        returns a string of the current length of the conversation and the approximate number of tokens
        '''
        tmp = len(await self.get_curr_gpt_thread())
        return f"len:{tmp} | tokens: ~{tmp/4}"
    
    # changing gptsettings
    async def modifygptset(self, msg : discord.message.Message, usr_msg : str) -> None:
        ''' 
        Executes both gptset and gptsettings (to print out the new gpt api params for the next call)
        expect format: gptset [setting_name] [new_value]

        Returns None if ok, else returns a error msg string.
        '''
        try:
            self.gptset(usr_msg, self.gpt_settings)
        except Exception as e:
            return "gptset: gptset [setting_name] [new_value]"
        return None
    
    def gpt_save_prompts_to_file(self) -> None:
        '''
        saves the prompt_name -> prompt dictionary to disk via pickling
        '''
        with open(self.gpt_prompts_file, "wb") as f:
            pickle.dump(self.map_promptname_to_prompt, f, protocol=pickle.HIGHEST_PROTOCOL)

    def gpt_read_prompts_from_file(self) -> None:
        '''
        reads all the prompts from the prompt file and stores them in self.all_gpt_available_prompts and the mapping
        '''
        # reset curr state of prompts
        self.all_gpt_available_prompts = [] # prompt names
        self.map_promptname_to_prompt = {} # prompt name -> prompt

        # load in all the prompts
        with open(self.gpt_prompts_file, "rb") as f:
            # load in the pickled object
            self.map_promptname_to_prompt = pickle.load(f)
            # get the list of prompts
            self.all_gpt_available_prompts = list(self.map_promptname_to_prompt.keys())

    def gpt_context_reset(self, prompt_name : str = None) -> None:
        '''
        resets the gpt context
        > takes an optional input 'prompt_name' that denotes which prompt to use after resetting the thread (None for current, else a str for a new prompt)
        > can be used at the start of program run and whenever a reset is wanted
        '''
        if prompt_name != None: 
            self.curr_prompt_name = prompt_name
            self.curr_prompt_str = self.map_promptname_to_prompt[self.curr_prompt_name]

        self.gpt_settings["messages"][0] = [] # reset messages, should be gc'd
        self.gpt_settings["messages"][0].append({"role":self.chatgpt_name, "content":self.curr_prompt_str})
    
    async def get_curr_gpt_thread(self) -> str:
        '''
        generates the current gpt conversation thread from the gptsettings messages list
        '''
        ret_str = ""
        for msg in self.gpt_settings["messages"][0]:
            ret_str += f"{msg['role']}: {msg['content']}\n" 
        return ret_str

    def gptsettings(self) -> str:
        '''
        returns the available gpt settings, their current values, and their data types
        excludes the possibly large messages list
        '''
        gpt_settings = self.gpt_settings
        return "".join([f"{key} ({gpt_settings[key][1]}) = {gpt_settings[key][0]}\n" for key in gpt_settings.keys() if key != "messages"])

    def gptset(self, usr_msg : str, options : str = None) -> None:
        '''
        format is 

        GPTSET, [setting_name], [new_value]

        sets the specified gpt parameter to the new value
        
        e.g.
        usr_msg = prompt, "bob the builder loves to build"
        '''
        tmp = usr_msg.split()
        setting, new_val = tmp[1], tmp[2]
        self.gpt_settings[setting][0] = new_val # always gonna store str

        # if setting a new model, update the max_tokens
        if setting == "model":
            x = self.gpt_model_to_max_tokens[new_val] # (max_tokens, date of latest date)
            self.gpt_settings["max_tokens"][0] = x[0]

    def get_all_gpt_prompts_as_str(self):
        '''
        constructs the string representing each [prompt_name, prompt] as one long string and return it
        '''
        return "".join([f"Name: {k}\nPrompt:{v}\n----\n" for k,v in self.map_promptname_to_prompt.items()])

