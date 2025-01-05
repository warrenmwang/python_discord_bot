from openai import OpenAI
import os
import pickle
import asyncio
from concurrent.futures import ThreadPoolExecutor
from Utils import constructHelpMsg, Message
import time
from PIL import Image
import io
import base64
from abc import ABC, abstractmethod

#################### Abstract Classes defining the common interface #################### 

class Image_Gen_Instance(ABC):
    @abstractmethod
    async def main(self, msg: Message) -> Image.Image:
        pass

class LLM_Instance(ABC):
    @abstractmethod
    async def main(self, msg: Message) -> str:
        pass

#################### Specific implementations that will implement the abstract classes #################### 

class Dalle(Image_Gen_Instance):
    def __init__(self):
        self.model = "dall-e-3"
        self.client = OpenAI()

    async def main(self, msg: Message) -> Image.Image:
        '''
        Create an image using Dalle from openai and return it as a base64-encoded image
        '''
        prompt = msg.content
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
        tmp = response.data[0].b64_json
        encoded_img = tmp if tmp is not None else ""
        image = Image.open(io.BytesIO(base64.b64decode(encoded_img)))

        # return image
        return image

class Stable_Diffusion(Image_Gen_Instance):
    def __init__(self):
        pass

    async def main(self, msg: Message) -> Image.Image:
        # TODO:
        return Image.new('RGB', (1024, 1024), color='black')

class OpenAI_LLM(LLM_Instance):
    def __init__(self, readPromptFile:bool=False, app_data_dir: str = './data', default_model: str = 'gpt-4o'):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        assert self.api_key != '', 'OPENAI_API_KEY environment variable not found.'
        self.app_data_dir = os.getenv("APP_DATA_DIR", "./data")

        self.client = OpenAI(api_key=self.api_key)

        # format: [max return tokens] [context length] [knowledge cutoff]
        self.gpt_models_info = {
            "gpt-4o": [4096, 128000, "Oct 2023"],
            "gpt-4-turbo": [4096, 128000, "Dec 2023"],
            "gpt-4-0125-preview": [4096, 128000, "Dec 2023"],
            "gpt-4-1106-preview": [4096, 128000, "Apr 2023"], 
            "gpt-4-vision-preview" : [4096, 128000, "Apr 2023"], 
            "gpt-4" : [8192, 8192, "Sep 2021"]
        }
        assert default_model in self.gpt_models_info.keys(), f"OpenAI_LLM: default_model {default_model} not available"

        # initial settings
        self.gpt_settings = {
            "model": [default_model, "str"], 
            "prompt": ["", "str"], # only used to show to user the current prompt.
            "messages" : [[], "list of dicts"],
            "temperature": ["0.0", "float"],
            "top_p": ["1.0", "float"],
            "frequency_penalty": ["0", "float"],
            "presence_penalty": ["0", "float"],
            "max_tokens": [self.gpt_models_info[default_model][0], "int"],
            "context_length": [self.gpt_models_info[default_model][1], "int"],
            "knowledge_cutoff": [self.gpt_models_info[default_model][2], "str"]
        }
        self.chatgpt_name="assistant"
        self.cmd_prefix = "!"

        # gpt prompts
        self.gpt_prompts_file = f"{app_data_dir}/gpt_prompts.txt"
        self.all_gpt_available_prompts = [] # list of all prompt names
        self.map_promptname_to_prompt = {} # dictionary of (k,v) = (prompt_name, prompt_as_str)
        self.curr_prompt_name = None  # name of prompt we're currently using
        self.hotswap_models = ["gpt-4-0125-preview", "gpt-4-vision-preview"] # for now not changeable.
        self.pickled_threads_dir = f"{app_data_dir}/pickled_threads"

        # modifying prompts
        self.modify_prompts_state = None
        self.modify_prompts_state_tmp = None
        self.personal_assistant_modify_prompts_buff = []

        self.commands = {
            "help (h)" : "display this message",
            "convo len (cl)" : 'show current gpt context length',
            "reset thread (rt)" : 'reset gpt context length',
            "show thread (st)" : 'show the entire current convo context',
            "gptsettings" : 'show the current gpt settings',
            "gptset": "format is `gptset [setting_name] [new_value]` modify gpt settings",
            "current prompt (cp)": "get the current prompt name",
            "change prompt (chp)": "format `change prompt, [new prompt name]`",
            "list prompts (lp)": "list the available prompts for gpt",
            "list models (lm)": "list the available gpt models",
            "modify prompts": "modify the prompts for gpt",
            "save thread": "save the current gptX thread to a file",
            "show old threads": "show the old threads that have been saved",
            "load thread": "format `load thread, [unique id]` load a gptX thread from a file",
            "delete thread": "format `delete thread, [unique id]` delete a gptX thread from a file",
            "current model (cm)": "show the current gpt model",
            "swap": f"hotswap btwn models: ({self.hotswap_models})",
        }
        self.commands_help_str = constructHelpMsg(self.commands)

        # initialize prompts
        if readPromptFile:
            self._gpt_read_prompts_from_file() # read the prompts from disk, if any, if enabled.
        self._init_empty_prompt() # at object instantiation, start with an empty system assistant prompt

    async def _gen_GPT_Response(self, msg : Message) -> str:
        '''
        retrieves a GPT response given a string input and a dictionary containing the settings to use
        checks for attachments in the discord Message construct
        returns the response str
        '''
        assert len(self.api_key) > 0, 'Empty API Key, cannot request GPT generation.'
        settings_dict = self.gpt_settings

        response_msg = ""

        # init content with the user's message
        content = [{ "type": "text", "text": msg.content }]

        # attachments 
        if msg.attachments is not None:
            for text in msg.attachments['texts']:
                content[0]['text'] = content[0]['text'] + "\n<FILECONTENTSTART>:\n" + text + "\n<FILECONTENTEND>"
            for imageB64str in msg.attachments['images']:
                image_dict = {"type": "image_url", "image_url": {"url" : f"data:image/jpeg;base64,{imageB64str}"}}
                content.append(image_dict)
            for pdf in msg.attachments['pdfs']:
                embedded_text, ocr_text = pdf.embedded_text, pdf.ocr_text
                content[0]['text'] = content[0]['text'] + "\n<PDFCONTENTSTART>" + "\nEMBEDDED TEXT:\n" + embedded_text + "\nOCR TEXT:\n" + ocr_text + "\n<PDFCONTENTEND>"

        new_usr_msg = {
            "role": "user",
            "content": content
        }

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
                max_tokens = int(settings_dict["max_tokens"][0])
            )

        # Run the blocking function in a separate thread using run_in_executor
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            completion = await loop.run_in_executor(executor, blocking_api_call)

        tmp = completion.choices[0].message.content
        chatgptcompletion = tmp if tmp is not None else ""
        response_msg += chatgptcompletion
        return response_msg

    def _add_and_set_prompt(self, promptName : str, promptStr : str, resetThread : bool = False) -> None:
        '''
        Set the current prompt (and add it into the available options if new) and
        if [resetThread] is passed as True, reset the current message thread, o.w. leave 
        the current thread alone.
        '''
        # altho assumption is that prompt is not already in system, if it is just move on
        # and set the prompt.
        if promptName not in self.all_gpt_available_prompts:
            self.map_promptname_to_prompt[promptName] = promptStr
            self.all_gpt_available_prompts.append(promptName)

        # set current prompt to this prompt
        self.curr_prompt_name = promptName
        self.gpt_settings["prompt"][0] = self.curr_prompt_name

        if resetThread:
            # gpt_context_reset initializes new thread prompt based off of the self.curr_prompt_name
            self._gpt_context_reset()
        else:
            self._set_prompt(self.curr_prompt_name)
    
    def _set_prompt(self, promptName : str) -> None:
        '''
        Assuming that the first message in the system is the system/assistant, 
        modify the content (prompt) to the requested prompt.
        '''
        assert promptName in self.all_gpt_available_prompts, "Requested promptName is not in system."
        self.curr_prompt_name = promptName

        # update prompt in the actual thread
        thread = self.gpt_settings["messages"][0]
        systemPromptMsg = thread[0]
        assert systemPromptMsg["role"] == self.chatgpt_name, "First message in thread is NOT the system prompt message. It should be."
        thread[0]["content"][0]["text"] = self.map_promptname_to_prompt[promptName]
        # and in the prompt note in the gptsettings
        self.gpt_settings["prompt"][0] = self.curr_prompt_name

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
            self._gpt_save_prompts_to_file() # write the new prompts to file
            self._gpt_read_prompts_from_file()
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return f"Updated '{prompt_name}' to '{new_prompt}'"
        if self.modify_prompts_state_tmp == "add":
            prompt_name = usr_msg.split("<SEP>")[0]
            prompt = usr_msg.split("<SEP>")[1]
            self.map_promptname_to_prompt[prompt_name] = prompt
            self._gpt_save_prompts_to_file() # write the new prompts to file
            self._gpt_read_prompts_from_file()
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return f"Added '{prompt_name}' with prompt '{prompt}'"
        if self.modify_prompts_state_tmp == "delete":
            prompt_name = usr_msg
            del self.map_promptname_to_prompt[prompt_name]
            self._gpt_save_prompts_to_file() # write the new prompts to file
            self._gpt_read_prompts_from_file()
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
            self._gpt_save_prompts_to_file() # write the new prompts to file
            self._gpt_read_prompts_from_file()
            self.modify_prompts_state = None
            self.modify_prompts_state_tmp = None
            return  f"Changed '{prompt_name}' to '{new_prompt_name}'"

        return "Error: unexpected modify prompts state."

    async def _modifyParams(self, usr_msg : str) -> str:
        '''
        Modifies ChatGPT API params.
        Returns the output of an executed command or returns an error/help message.
        Is only accessed if usr_msg is a command.
        '''
        # convert shortcut to full command if present
        usr_msg = self._shortcut_cmd_convertor(usr_msg)

        # if in middle of modifying prompts
        if self.modify_prompts_state is not None:
            return await self._modify_prompts(usr_msg)

        # help
        if usr_msg == "help":
            return self.commands_help_str

        # save current msg log to file 
        if usr_msg == "save thread":
            global time
            # pickle the current thread from gptsettings["messages"][0]
            msgs_to_save = self.gpt_settings["messages"][0]
            # grab current time in nanoseconds
            curr_time = time.time()
            # pickle the msgs_to_save and name it the current time
            with open(f"{self.pickled_threads_dir}/{curr_time}.pkl", "wb") as f:
                pickle.dump(msgs_to_save, f, protocol=pickle.HIGHEST_PROTOCOL)
            return f"Saved thread to file as {curr_time}.pkl"
 
        # show old threads that have been saved
        if usr_msg == "show old threads":
            ret_str = ""
            # for now, list all the threads...
            for filename in os.listdir(self.pickled_threads_dir):
                # read the file and unpickle it
                with open(f"{self.pickled_threads_dir}/{filename}", "rb") as f:
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
            with open(f"{self.pickled_threads_dir}/{thread_id}.pkl", "rb") as f:
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
            os.remove(f"{self.pickled_threads_dir}/{thread_id}.pkl")
            return f"Deleted thread {thread_id}.pkl"

        # list available models of interest
        if usr_msg == "list models":
            tmp = "".join([f"{k}: {v}\n" for k,v in self.gpt_models_info.items()])
            ret_str = f"Available models:\n{tmp}" 
            return ret_str

        # show the current gpt prompt
        if usr_msg == "current prompt":
            return self.curr_prompt_name if self.curr_prompt_name is not None else "Current prompt is not initialized."

        # just show current model
        if usr_msg == "current model":
            return f"Current model: {self.gpt_settings['model'][0]}"

        # toggle which model to use (toggle between the latest gpt4 turbo and the vision model)
        if usr_msg == "swap":
            curr_model = self.gpt_settings["model"][0]
            if curr_model == "gpt-4-vision-preview":
                await self._modifygptset("gptset model gpt-4-0125-preview")
            else:
                await self._modifygptset("gptset model gpt-4-vision-preview")
            return f'Set to: {self.gpt_settings["model"][0]}'

        # add a command to add a new prompt to the list of prompts and save to file
        if usr_msg == "modify prompts":
            if self.modify_prompts_state is None:
                self.modify_prompts_state = "modify prompts"
                self.modify_prompts_state_tmp = "asked what to do" 
                return f"These are the existing prompts:\n{self._get_all_gpt_prompts_as_str()}\nDo you want to edit an existing prompt, add a new prompt, delete a prompt, or change a prompt's name? (`edit` `add` `delete` `changename`)\nNote that you should preface inputs with the command prefix char. You can also stop this process with `cancel`"

        # directly add a new prompt, reset curr thread, and use this new prompt in subsequent refreshes
        # format is `!_add_and_set_prompt<SEP>[prompt name]<SEP>[prompt string]<SEP>[reset thread bool]`
        if usr_msg.startswith("_add_and_set_prompt"):
            tmp = usr_msg.split("<SEP>")
            prompt_name = tmp[1]
            prompt_str = tmp[2]
            reset_thread_bool = tmp[3]
            try:
                reset_thread_bool = bool(reset_thread_bool)
            except Exception:
                reset_thread_bool = False
            self._add_and_set_prompt(prompt_name, prompt_str, reset_thread_bool)

        # change gpt prompt
        if usr_msg[:13] == "change prompt":
            # accept only the prompt name, update both str of msgs context and the messages list in gptsettings
            print(usr_msg)
            new_prompt_name = list(map(str.strip, usr_msg.split(',')))[1]
            if new_prompt_name not in self.all_gpt_available_prompts:
                return f"Prompt {new_prompt_name} not available. Available prompts: {' '.join(self.all_gpt_available_prompts)}"
            self._set_prompt(promptName=new_prompt_name)
            return "New current prompt set to: " + new_prompt_name

        # show available prompts as (ind. prompt)
        if usr_msg == "list prompts":
            return self._get_all_gpt_prompts_as_str()

        # show user current gpt settings
        if usr_msg == "gptsettings":
            return self._gptsettings()

        # user wants to modify gpt settings
        if usr_msg[0:6] == "gptset":
            await self._modifygptset(usr_msg)
            return self._gptsettings()

        # show the current thread
        if usr_msg == "show thread":
            return await self._get_curr_gpt_thread()

        # reset the current convo with the curr prompt context
        if usr_msg == "reset thread":
            self._gpt_context_reset()
            return f"Thread Reset. {await self._get_curr_convo_len_and_approx_tokens()}"

        # check curr convo context length
        if usr_msg == "convo len":
            return await self._get_curr_convo_len_and_approx_tokens()

        # format: `_add_msg_to_curr_thread<SEP>[role]<SEP>[content]`
        if usr_msg.startswith("_add_msg_to_curr_thread"):
            x = usr_msg.split("<SEP>")
            role, content = x[1], x[2]
            self._add_msg_to_curr_thread(role, content)
            return "[assistant]: command completed."

        return "Unknown command."

    def _shortcut_cmd_convertor(self, usr_msg :str) -> str:
        '''
        If the user enters a shortcut command, convert it to the actual command.
        This function is only accessed if the usr_msg is recognized as a command (is prefixed by the command prefix symbol).
        '''
        shortcut_map = {
            "h": "help",
            "rt": "reset thread", 
            "cl": "convo len",
            "st": "show thread",
            "cp": "current prompt",
            "lm": "list models",
            "cm": "current model", 
            "lp": "list prompts",
            "save": "save thread"
        }
        if usr_msg in shortcut_map:
            return shortcut_map[usr_msg]

        if usr_msg[:3] == "chp":
            return "change prompt" + usr_msg[3:]
        if usr_msg[:4] == "load" and usr_msg[5:11] != "thread":
            return "load thread" + usr_msg[3:]

        # not a shortcut command
        return usr_msg

    async def _get_curr_convo_len_and_approx_tokens(self) -> str:
        '''
        Returns a string of the current length of the conversation and the approximate number of tokens
        as a single string
        '''
        tmp = len(await self._get_curr_gpt_thread())
        return f"len:{tmp} | tokens: ~{tmp/4}"

    async def _modifygptset(self, usr_msg : str) -> None | str:
        '''
        Executes both gptset and gptsettings (to print out the new gpt api params for the next call)
        expect format: gptset [setting_name] [new_value]

        Returns None if ok, else returns a error msg string.
        '''
        # also allow user to user command like gptset, [setting_name], [new_value]
        if ',' in usr_msg:
            usr_msg = usr_msg.replace(',', ' ')

        try:
            self._gptset(usr_msg)
        except Exception as _:
            return "gptset: gptset [setting_name] [new_value]"
        return None

    def _gpt_save_prompts_to_file(self) -> None:
        '''
        saves the prompt_name -> prompt dictionary to disk via pickling
        > not thread safe
        '''
        with open(self.gpt_prompts_file, "w") as f:
            # save the prompts to disk
            for k,v in self.map_promptname_to_prompt.items():
                f.write(f"{k}<SEP>{v}\n")

    def _gpt_read_prompts_from_file(self) -> None:
        '''
        reads all the prompts from the prompt file and stores them in self.all_gpt_available_prompts and the mapping
        > not thread safe
        '''
        # reset curr state of prompts
        self.all_gpt_available_prompts = [] # prompt names
        self.map_promptname_to_prompt = {} # prompt name -> prompt

        # quit if prompt file doesn't exist
        if not os.path.exists(self.gpt_prompts_file):
            return

        # load in all the prompts
        with open(self.gpt_prompts_file, "r") as f:
            # read the plain text prompts file, should be in format:
            # [prompt_name]<SEP>[prompt]
            lines = f.readlines()
            for line in lines:
                tmp = line.split("<SEP>")
                prompt_name = tmp[0].strip()
                prompt = tmp[1].strip()
                self.map_promptname_to_prompt[prompt_name] = prompt
                self.all_gpt_available_prompts.append(prompt_name)

    def _init_empty_prompt(self) -> None:
        '''inits an empty prompt for the message thread, if not present in prompts listing'''
        # add empty prompt if not present
        if 'empty' not in self.all_gpt_available_prompts:
            self.map_promptname_to_prompt['empty'] = ''
            self.all_gpt_available_prompts.append('empty')

        # initialize thread with empty system/assistant prompt
        self.curr_prompt_name = "empty" # Default to an empty prompt, if not present in user's prompts list, append it
        self.gpt_settings["prompt"][0] = self.curr_prompt_name
        self._gpt_context_reset(prompt_name=self.curr_prompt_name)

    def _gpt_context_reset(self, prompt_name : str | None = None) -> None:
        '''
        Resets the gpt context.
        Takes an optional argument that is the [prompt_name] used as a key to retrieve the 
        prompt string from the hashmap / dictionary [self.map_promptname_to_prompt] that seeds
        the new, empty thread (list of messages) as the system assistant's prompt. If the [prompt_name]
        is not provided, the [self.curr_prompt_name] is used to retrieve the current set prompt's string.
        '''
        if prompt_name is not None: 
            self.curr_prompt_name = prompt_name
            self.curr_prompt_str = self.map_promptname_to_prompt[self.curr_prompt_name]

        self.curr_prompt_str = self.map_promptname_to_prompt[self.curr_prompt_name]
        self.gpt_settings["messages"][0] = [] # reset messages, old messages should be gc'd
        # add the first message in thread: the system prompt
        self._add_msg_to_curr_thread(self.chatgpt_name, self.curr_prompt_str) 

    async def _get_curr_gpt_thread(self) -> str:
        '''
        Generates the current gpt conversation thread as a string from the gptsettings messages list
        Notably, we know that images and pdf representations are in their raw string form (base64 encoded str for images,
        embedded text and ocr text for pdfs). Therefore, we shorten those to just [image] and [pdf] respectively.
        '''
        ret_str = ""
        messages = self.gpt_settings["messages"][0]

        for msg in messages:
            content = msg["content"]

            if len(content) == 0:
                continue # skip empty messages

            currMsgTxt = f'{msg["role"]}: \n'
            for c in content:
                type = c["type"]
                if type == "text":
                    currMsgTxt += f'{c["text"]}\n'
                elif type == "image_url":
                    currMsgTxt += '[image]\n'
                elif type == "pdf":
                    currMsgTxt += '[pdf]\n'
            ret_str += currMsgTxt
        return ret_str

    def _gptsettings(self) -> str:
        '''
        returns the available gpt settings, their current values, and their data types
        excludes the possibly large messages list
        '''
        gpt_settings = self.gpt_settings
        return "".join([f"{key} ({gpt_settings[key][1]}) = {gpt_settings[key][0]}\n" for key in gpt_settings.keys() if key != "messages"])

    def _gptset(self, usr_msg : str) -> None:
        '''
        Updates the gpt settings object used for GPT completions. Format is GPTSET [setting_name] [new_value].
        Sets the specified gpt parameter to the new value.
            e.g.
            usr_msg = prompt, "bob the builder loves to build"
        '''
        tmp = usr_msg.split()
        setting, new_val = tmp[1], tmp[2]
        self.gpt_settings[setting][0] = new_val # always gonna store str

        # if setting a new model, update the max_tokens
        if setting == "model":
            x = self.gpt_models_info[new_val] # (max return tokens, date of latest date)
            self.gpt_settings["max_tokens"][0] = x[0]
            self.gpt_settings["knowledge_cutoff"][0] = x[2]

    def _get_all_gpt_prompts_as_str(self) -> str:
        '''
        constructs the string representing each [prompt_name, prompt] as one long string and return it
        '''
        return "".join([f"Name: {k}\nPrompt:{v}\n----\n" for k,v in self.map_promptname_to_prompt.items()])

    def _add_msg_to_curr_thread(self, role:str, content:str) -> None:
        '''
        Add the new message, formatted for openai's GPT API, to the current context thread.
        '''
        msg = {"role": role, "content": [{"type": "text", "text": content}]}
        self.gpt_settings["messages"][0].append(msg)

    async def main(self, msg: Message) -> str:
        '''
        Entrance function for all ChatGPT API things.
        Either modifies the parameters or generates a response based off of current context and new user message.
        Returns the generation.
        '''
        usr_msg = msg.content
        if len(usr_msg) > 0:
            # catch if is a command
            if usr_msg[0] == self.cmd_prefix:
                if len(usr_msg) == 1:
                    return "Empty command provided."
                # pass to PA block without the prefix
                return await self._modifyParams(usr_msg[1:])

        # check to see if we are running out of tokens for current msg log
        # get the current thread length
        curr_thread = await self._get_curr_gpt_thread()
        curr_thread_len_in_tokens = len(curr_thread) / 4 # 1 token ~= 4 chars
        while curr_thread_len_in_tokens > int(self.gpt_settings["context_length"][0]):
            # remove the 2nd oldest message from the thread (first oldest is the prompt)
            self.gpt_settings["messages"][0].pop(1)

        # use usr_msg to generate new response from API
        gpt_response = await self._gen_GPT_Response(msg)

        # add gpt response to current thread
        self._add_msg_to_curr_thread(self.chatgpt_name, gpt_response)

        return gpt_response

class Anthropic_LLM(LLM_Instance):
    def __init__(self):
        pass

    async def main(self, msg: Message) -> str:
        return "Anthropic LLM: TODO not yet implemented"

#################### Control Classes #################### 

class Image_Gen_Controller():
    def __init__(self, init_provider_name: str = "openai"):
        self.curr_provider = init_provider_name
        self.providers = {
            "openai": Dalle(),
            "stable diffusion": Stable_Diffusion()
        }
        self.command_prefix = "$"

    # TODO: use this
    def swap_providers(self, new_provider: str) -> None:
        self.curr_provider = new_provider

    async def main(self, msg: Message) -> Image.Image:
        return await self.providers[self.curr_provider].main(msg)

class LLM_Controller():
    def __init__(self, init_provider_name: str = "openai"):
        self.curr_provider = init_provider_name
        self.providers = {
            "openai": OpenAI_LLM(),
            "anthropic": Anthropic_LLM()
        }
        self.command_prefix = "$"
        self.commands = {
            "help": "show this message",
            "providers": "shows a list of the available providers"
        }
        self.help_msg = constructHelpMsg(self.commands)

    # TODO: use this
    def swap_providers(self, new_provider: str) -> None:
        self.curr_provider = new_provider

    async def main(self, msg: Message) -> str:
        if msg.content.startswith("$"):
            cmd = msg.content[1:].strip().lower()
            if cmd == "help":
                return self.help_msg
            if cmd == "providers":
                return "\n".join(list(self.providers.keys()))
            return "[LLM Controller] -- Unknown command"

        return await self.providers[self.curr_provider].main(msg)
