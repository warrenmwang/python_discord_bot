import discord, asyncio, os, openai, requests
import io, base64
from concurrent.futures import ThreadPoolExecutor
import pickle, time
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

class BMO:
    def __init__(self):
        # api keys
        self.TOKEN = os.getenv('DISCORD_TOKEN')
        self.GPT3_OPENAI_API_KEY = os.getenv("GPT3_OPENAI_API_KEY")

        # gpt
        self.gpt3_channel_name = os.getenv('GPT3_CHANNEL_NAME')
        self.gpt3_channel_id = os.getenv('GPT3_CHANNEL_ID')
        self.gpt3_settings = {
            "model": ["gpt-3.5-turbo", "str"],
            "messages" : [[], "list of dicts"],
            "temperature": ["0.0", "float"],
            "top_p": ["1.0", "float"],
            "frequency_penalty": ["0", "float"],
            "presence_penalty": ["0", "float"],
            "max_tokens": ["4096", "int"],
        }
        self.discord_msglen_cap = 2000
        self.chatgpt_name="assistant"
        self.gpt3_model_to_max_tokens = {
            "gpt-3.5-turbo": 4096,
            "gpt-4": 8192,
            "gpt-4-32k": 32768
        }
        self.cmd_prefix = "!"

        # stable diffusion
        self.stable_diffusion_channel = os.getenv('STABLE_DIFFUSION_CHANNEL')
        self.stable_diffusion_output_dir = os.getenv('STABLE_DIFFUSION_OUTPUT_DIR')

        # personal assistant
        self.personal_assistant_channel = os.getenv('PERSONAL_ASSISTANT_CHANNEL')
        self.personal_assistant_state = None
        self.personal_assistant_modify_prompts_state = None
        self.personal_assistant_modify_prompts_buff = []

        # gpt prompts
        self.gpt_prompts_file = os.getenv("GPT_PROMPTS_FILE") # pickled prompt name -> prompts dict
        self.all_gpt3_available_prompts = None # list of all prompt names
        self.map_promptname_to_prompt = None # dictionary of (k,v) = (prompt_name, prompt_as_str)
        self.curr_prompt_name = None  # name of prompt we're currently using

        # ignore any messages not in these channels
        self.allowed_channels = [self.gpt3_channel_name, self.personal_assistant_channel, self.stable_diffusion_channel]

        # discord
        self.intents = discord.Intents.all()
        self.client = discord.Client(intents=self.intents)

    ############################## GPT3 ##############################

    def gpt_save_prompts_to_file(self) -> None:
        '''
        saves the prompt_name -> prompt dictionary to disk via pickling
        '''
        with open(self.gpt_prompts_file, "wb") as f:
            pickle.dump(self.map_promptname_to_prompt, f, protocol=pickle.HIGHEST_PROTOCOL)

    async def gpt_read_prompts_from_file(self) -> None:
        '''
        reads all the prompts from the prompt file and stores them in self.all_gpt3_available_prompts and the mapping
        '''
        # reset curr state of prompts
        self.all_gpt3_available_prompts = [] # prompt names
        self.map_promptname_to_prompt = {} # prompt name -> prompt

        # load in all the prompts
        with open(self.gpt_prompts_file, "rb") as f:
            # load in the pickled object
            self.map_promptname_to_prompt = pickle.load(f)
            # get the list of prompts
            self.all_gpt3_available_prompts = list(self.map_promptname_to_prompt.keys())

    async def gpt_prompt_initializer(self) -> None:
        '''
        loads in all the prompts from the prompt file
        '''
        # read the prompts from disk
        await self.gpt_read_prompts_from_file()
        # init with first prompt
        self.curr_prompt_name = self.all_gpt3_available_prompts[0]
        await self.gpt_context_reset()

    async def gpt_context_reset(self) -> None:
        '''
        resets the gpt3 context
        > can be used at the start of program run and whenever a reset is wanted
        '''
        self.gpt3_settings["messages"][0] = [] # reset messages, should be gc'd
        self.gpt3_settings["messages"][0].append({"role":self.chatgpt_name, "content":self.map_promptname_to_prompt[self.curr_prompt_name]})
    
    async def get_curr_gpt_thread(self) -> str:
        '''
        generates the current gpt conversation thread from the gptsettings messages list
        '''
        ret_str = ""
        for msg in self.gpt3_settings["messages"][0]:
            ret_str += f"{msg['role']}: {msg['content']}\n" 
        return ret_str

    async def gen_gpt3(self, usr_msg : str, settings_dict: dict = None) -> str:
        '''
        retrieves a GPT3 response given a string input and a dictionary containing the settings to use
        returns the response str
        '''

        if settings_dict is None:
            settings_dict = self.gpt3_settings

        # update log(list) of messages, then use it to query
        settings_dict["messages"][0].append({"role": "user", "content": usr_msg})

        def blocking_api_call():
            # query
            return openai.ChatCompletion.create(
                model = settings_dict["model"][0],
                messages = settings_dict["messages"][0],
                temperature = float(settings_dict["temperature"][0]),
                top_p = float(settings_dict["top_p"][0]),
                frequency_penalty = float(settings_dict["frequency_penalty"][0]),
                presence_penalty = float(settings_dict["presence_penalty"][0]),
            )
        
        # Run the blocking function in a separate thread using run_in_executor
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, blocking_api_call)

        return response['choices'][0]['message']['content']

    async def gptsettings(self, msg : discord.message.Message, gpt3_settings : dict) -> None:
        '''
        prints out all available gpt3 settings, their current values, and their data types
        excludes the possibly large messages list
        '''
        await self.send_msg_to_usr(msg, "".join([f"{key} ({gpt3_settings[key][1]}) = {gpt3_settings[key][0]}\n" for key in gpt3_settings.keys() if key != "messages"]))

    async def gptset(self, usr_msg : str, gpt3_settings : dict) -> None:
        '''
        original call is:
            GPTSET [setting_name] [new_value]

        sets the specified gpt3 parameter to the new value
        '''
        tmp = usr_msg.split()
        setting, new_val = tmp[1], tmp[2]
        gpt3_settings[setting][0] = new_val # always gonna store str

        # if setting a new model, update the max_tokens
        if setting == "model":
            gpt3_settings["max_tokens"][0] = self.gpt3_model_to_max_tokens[new_val]

    def get_all_gpt_prompts_as_str(self):
        '''
        constructs the string representing each [prompt_name, prompt] as one long string and return it
        '''
        return "".join([f"Name: {k}\nPrompt:{v}\n----\n" for k,v in self.map_promptname_to_prompt.items()])
        
    async def send_msg_to_usr(self, msg : discord.message.Message, usr_msg : str): 
        '''
        in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
        the damn message (whether it be one or multiple messages)
        '''
        diff = len(usr_msg)
        start = 0
        end = self.discord_msglen_cap
        while diff > 0:
            await msg.channel.send(usr_msg[start:end])
            start = end
            end += self.discord_msglen_cap
            diff -= self.discord_msglen_cap

    async def send_img_to_usr(self, msg : discord.message.Message, imgPath : str):
        '''given the image path in the filesystem, send it to the author of the msg'''
        await msg.channel.send(file=discord.File(imgPath))
    ############################## GPT3 ##############################

    ############################## Personal Assistant ##############################
    async def personal_assistant_block(self, msg : discord.message.Message, usr_msg: str) -> None:
        '''
        Custom commands that do a particular hard-coded thing.
        '''

        ######## PA funcs ########

        def _pa_shortcut_cmd_convertor(usr_msg :str) -> str:
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
            if usr_msg == "lm":
                return "list models"
            if usr_msg == "cm":
                return "current model"

            # not a shortcut command
            return usr_msg

        async def _pa_modify_prompts(self, msg : discord.message.Message, usr_msg : str) -> None:
            '''
            handles changing the prompts for the personal assistant
            '''
            # user can cancel at any time
            if usr_msg == "cancel":
                # cancel modifying any prompts
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                self.personal_assistant_modify_prompts_buff = []
                await self.send_msg_to_usr(msg, "Ok, cancelling.")
                return

            # Stage 1: usr picks a operator
            if self.personal_assistant_modify_prompts_state == "asked what to do":
                # check response
                if usr_msg == "edit":
                    self.personal_assistant_modify_prompts_state = "edit"
                    await self.send_msg_to_usr(msg, "Ok which prompt would you like to edit? [enter prompt name]")
                    return
                elif usr_msg == "add":
                    self.personal_assistant_modify_prompts_state = "add"
                    await self.send_msg_to_usr(msg, "Ok, write a prompt in this format: [name]<SEP>[PROMPT] w/o the square brackets.")
                    return
                elif usr_msg == "delete":
                    self.personal_assistant_modify_prompts_state = "delete"
                    await self.send_msg_to_usr(msg, "Ok, which prompt would you like to delete? [enter prompt name]")
                    return
                elif usr_msg == "changename":
                    self.personal_assistant_modify_prompts_state = "changename"
                    await self.send_msg_to_usr(msg, "Ok, which prompt name would you like to rename? [enter prompt name]")
                    return
                else:
                    await self.send_msg_to_usr(msg, "Invalid response, please try again.")
                    return

            # Stage 2: usr provides more info for an already chosen operator
            if self.personal_assistant_modify_prompts_state == "edit":
                await self.send_msg_to_usr(msg, f"Ok, you said to edit {usr_msg}.\nSend me the new prompt for this prompt name. (just the new prompt in its entirety)")
                self.personal_assistant_modify_prompts_buff.append(usr_msg)
                self.personal_assistant_modify_prompts_state = "edit2"
                return
            if self.personal_assistant_modify_prompts_state == "edit2":
                # update our mapping of prompt name to prompt dict, then write the new prompts to file
                prompt_name = self.personal_assistant_modify_prompts_buff.pop()
                new_prompt = usr_msg
                self.map_promptname_to_prompt[prompt_name] = new_prompt
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await self.send_msg_to_usr(msg, f"Updated '{prompt_name}' to '{new_prompt}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
            if self.personal_assistant_modify_prompts_state == "add":
                await self.send_msg_to_usr(msg, f"Ok, you said to add '{usr_msg}'...")
                prompt_name = usr_msg.split("<SEP>")[0]
                prompt = usr_msg.split("<SEP>")[1]
                self.map_promptname_to_prompt[prompt_name] = prompt
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await self.send_msg_to_usr(msg, f"Added '{prompt_name}' with prompt '{prompt}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
            if self.personal_assistant_modify_prompts_state == "delete":
                await self.send_msg_to_usr(msg, f"Ok, you said to delete '{usr_msg}'...")
                prompt_name = usr_msg
                del self.map_promptname_to_prompt[prompt_name]
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await self.send_msg_to_usr(msg, f"Deleted '{prompt_name}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
            if self.personal_assistant_modify_prompts_state == "changename":
                self.personal_assistant_modify_prompts_buff.append(usr_msg)
                self.personal_assistant_modify_prompts_state = "changename2"
                await self.send_msg_to_usr(msg, f"Ok, what would you like to change the {usr_msg} to?")
                return
            if self.personal_assistant_modify_prompts_state == "changename2":
                prompt_name = self.personal_assistant_modify_prompts_buff.pop()
                new_prompt_name = usr_msg
                prompt = self.map_promptname_to_prompt[prompt_name]
                del self.map_promptname_to_prompt[prompt_name]
                self.map_promptname_to_prompt[new_prompt_name] = prompt
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await self.send_msg_to_usr(msg, f"Changed '{prompt_name}' to '{new_prompt_name}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
        
        # convo len
        async def _pa_get_curr_convo_len_and_approx_tokens(self) -> str:
            '''
            returns a string of the current length of the conversation and the approximate number of tokens
            '''
            tmp = len(await self.get_curr_gpt_thread())
            return f"len:{tmp} | tokens: ~{tmp/4}"
        
        # changing gptsettings
        async def _pa_gptset(self, msg, usr_msg):
            ''' expect format: gptset [setting_name] [new_value]'''
            try:
                await self.gptset(usr_msg, self.gpt3_settings)
                await self.gptsettings(msg, self.gpt3_settings)
            except Exception as e:
                await msg.channel.send("gptset: gptset [setting_name] [new_value]")
            return

        ############################

        # handle personal assistant state (if any)
        if self.personal_assistant_state == "modify prompts":
            await _pa_modify_prompts(self, msg, usr_msg)
            return

        # convert shortcut to full command if present
        usr_msg = _pa_shortcut_cmd_convertor(usr_msg)

        # alpaca
        if usr_msg[:6].lower() == "alpaca":
            prompt = usr_msg[7:]

            # don't generate for empty messages
            if len(prompt) == 0:
                await self.send_msg_to_usr(msg, "alpaca got empty message, abort generating response")
                return

            await self.send_msg_to_usr(msg, f"Generating a response to the prompt: {prompt}")
            await self.alpaca(msg, prompt)
            return

        # all commands below this are not case sensitive to the usr_msg so just lowercase it
        usr_msg = usr_msg.lower()

        # list all the commands available
        if usr_msg == "help":
            help_str = \
            "List of available commands:\n\
            help: show this message\n\
            remind me: set a reminder that will ping you in a specified amount of time\n\n\
            \
            GPT Settings:\n\
            convo len: show current gpt3 context length\n\
            reset thread: reset gpt3 context length\n\
            show thread: show the entire current convo context\n\
            gptsettings: show the current gpt3 settings\n\
            gptreplsettings: show gpt3 repl settings\n\
            gptset [setting_name] [new_value]: modify gpt3 settings\n\
            gptreplset [setting_name] [new_value]: modify gpt3 repl settings\n\
            curr prompt: get the current prompt name\n\
            change prompt, [new prompt]: change prompt to the specified prompt(NOTE: resets entire message thread)\n\
            show prompts: show the available prompts for gpt3\n\
            list models: list the available gpt models\n\
            modify prompts: modify the prompts for gpt\n\
            save thread: save the current gptX thread to a file\n\
            show old threads: show the old threads that have been saved\n\
            load thread [unique id]: load a gptX thread from a file\n\
            delete thread [unique id]: delete a gptX thread from a file\n\
            current model: show the current gpt model\n\
            swap: swap between gpt3.5 and gpt4 (regular)\n\n\
            "
            await msg.channel.send(help_str)
            return
        
        # just show current model
        if usr_msg == "current model":
            await msg.channel.send(f"Current model: {self.gpt3_settings['model'][0]}")
            return
        
        # swap between gpt3.5 and gpt4
        if usr_msg == "swap":
            curr_model = self.gpt3_settings["model"][0]
            if curr_model == "gpt-3.5-turbo":
                await _pa_gptset(self, msg, "gptset model gpt-4")
            else:
                await _pa_gptset(self, msg, "gptset model gpt-3.5-turbo")
            return

        # save current msg log to file 
        if usr_msg == "save thread":
            global time
            # pickle the current thread from gptsettings["messages"][0]
            msgs_to_save = self.gpt3_settings["messages"][0]
            # grab current time in nanoseconds
            curr_time = time.time()
            # pickle the msgs_to_save and name it the current time
            with open(f"./pickled_threads/{curr_time}.pkl", "wb") as f:
                pickle.dump(msgs_to_save, f, protocol=pickle.HIGHEST_PROTOCOL)
            await self.send_msg_to_usr(msg, f"Saved thread to file as {curr_time}.pkl")
            return

        # show old threads that have been saved
        if usr_msg == "show old threads":
            # for now, list all the threads...
            for filename in os.listdir("./pickled_threads"):
                # read the file and unpickle it
                with open(f"./pickled_threads/{filename}", "rb") as f:
                    msgs_to_load = pickle.load(f)
                    await self.send_msg_to_usr(msg, f"Thread id: {filename}")
                    for tmp in msgs_to_load:
                        tmp_role = tmp["role"]
                        tmp_msg = tmp["content"]
                        await self.send_msg_to_usr(msg, f"###{tmp_role.capitalize()}###\n{tmp_msg}\n###################\n")
            return

        # load msg log from file
        if usr_msg[:11] == "load thread":
            thread_id = usr_msg.split(" ")[2].strip()

            if len(thread_id) == 0:
                await self.send_msg_to_usr(msg, "No thread id specified")
                return

            if thread_id[-4:] == ".pkl":
                thread_id = thread_id[:-4]

            # read the file and unpickle it
            with open(f"./pickled_threads/{thread_id}.pkl", "rb") as f:
                msgs_to_load = pickle.load(f)
                # set the current gptsettings messages to this 
                self.gpt3_settings["messages"][0] = msgs_to_load
            await self.send_msg_to_usr(msg, f"Loaded thread {thread_id}.pkl") 
            return
        
        # delete a saved thread
        if usr_msg[:13] == "delete thread":
            thread_id = usr_msg[14:].strip()

            if len(thread_id) == 0:
                await self.send_msg_to_usr(msg, "No thread id specified")
                return

            # delete the file
            os.remove(f"./pickled_threads/{thread_id}.pkl")
            await self.send_msg_to_usr(msg, f"Deleted thread {thread_id}.pkl")
            return

        # list available models of interest
        if usr_msg == "list models":
            tmp = "".join([f"{k}: {v}\n" for k,v in self.gpt3_model_to_max_tokens.items()])
            await self.send_msg_to_usr(msg, f"Available models:\n{tmp}")
            return

        # show the current gpt3 prompt
        if usr_msg == "curr prompt":
            await msg.channel.send(self.curr_prompt_name)
            return

        # add a command to add a new prompt to the list of prompts and save to file
        if usr_msg == "modify prompts":
            if self.personal_assistant_state is None:
                self.personal_assistant_state = "modify prompts"
                self.personal_assistant_modify_prompts_state = "asked what to do" 
                await self.send_msg_to_usr(msg, f"These are the existing prompts:\n{self.get_all_gpt_prompts_as_str()}\nDo you want to edit an existing prompt, add a new prompt, delete a prompt, or change a prompt's name? (edit/add/delete/changename)")
                return

        # change gpt3 prompt
        if usr_msg[:13] == "change prompt":
            # accept only the prompt name, update both str of msgs context and the messages list in gptsettings
            try:
                self.curr_prompt_name = list(map(str.strip, usr_msg.split(',')))[1]
                await self.gpt_context_reset()
                await msg.channel.send("New current prompt set to: " + self.curr_prompt_name)
                return
            except Exception as e:
                await msg.channel.send("usage: change prompt, [new prompt]")
                return

        # show available prompts as (ind. prompt)
        if usr_msg == "show prompts":
            await self.send_msg_to_usr(msg, self.get_all_gpt_prompts_as_str())
            return 

        # show user current GPT3 settings
        if usr_msg == "gptsettings":
            await self.gptsettings(msg, self.gpt3_settings)
            return

        # user wants to modify GPT3 settings
        if usr_msg[0:6] == "gptset":
            await _pa_gptset(self, msg, usr_msg)
            return 
        
        # show the current thread
        if usr_msg == "show thread":
            # curr_thread = await self.get_curr_gpt_thread()
            # await self.send_msg_to_usr(msg, curr_thread)
            for tmp in self.gpt3_settings["messages"][0]:
                tmp_role = tmp["role"]
                tmp_msg = tmp["content"]
                await self.send_msg_to_usr(msg, f"###{tmp_role.capitalize()}###\n{tmp_msg}\n###################\n")
            return

        # reset the current convo with the curr prompt context
        if usr_msg == "reset thread":
            await self.gpt_context_reset()
            await msg.channel.send(f"Thread Reset. {await _pa_get_curr_convo_len_and_approx_tokens(self)}")
            return
        
        # check curr convo context length
        if usr_msg == "convo len":
            await self.send_msg_to_usr(msg, await _pa_get_curr_convo_len_and_approx_tokens(self))
            return

        # Reminders based on a time
        if usr_msg[0:9] == "remind me":
            try:
                tmp = list(map(str.strip, usr_msg.split(',')))
                task, time, unit = tmp[1], float(tmp[2]), tmp[3]
                if unit == "s":
                    remind_time = time
                elif unit == "m":
                    remind_time = time * 60
                elif unit == "h":
                    remind_time = time * 3600
                elif unit == "d":
                    remind_time = time * 86400
                else:
                    await msg.channel.send("only time units implemented: s, m, h, d")
                    return

                await self.send_msg_to_usr(msg, f"Reminder set for '{task}' in {time} {unit}.")
                await asyncio.sleep(remind_time)
                await self.send_msg_to_usr(msg, f"REMINDER: {task}")
            except Exception as e:
                await self.send_msg_to_usr(msg, "usage: remind me, [task_description], [time], [unit]")
            return

        await self.send_msg_to_usr(msg, "Type 'help' for a list of commands.")

    ############################## Personal Assistant ##############################

    ############################## Stable Diffusion ##############################
    async def sd_text2img(self, msg : discord.message.Message, usr_msg : str) -> None:
        '''
        ping the localhost stablediffusion api 
        '''
        payload = {
            "prompt": usr_msg,
            "steps": 20
        }
        await self.send_msg_to_usr(msg, f"Creating image of \"{usr_msg}\"")

        response = requests.post(url=f'http://127.0.0.1:7860/sdapi/v1/txt2img', json=payload)
        r = response.json()
        for i in r['images']:
            image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
            image.save(self.stable_diffusion_output_dir)
            await self.send_img_to_usr(msg, self.stable_diffusion_output_dir)

    ############################## Main Function ##############################

    def run_discord_bot(self):
        '''
        Main function
        '''
        ########################### INIT ############################
        @self.client.event
        async def on_ready():
            '''
            When ready, load all looping functions if any.
            '''
            print(f'{self.client.user} running!')
            await self.gpt_prompt_initializer()
            openai.api_key = self.GPT3_OPENAI_API_KEY

        ########################### ON ANY MSG ############################

        @self.client.event
        async def on_message(msg : discord.message.Message):
            '''
            Entrance function for any message sent to any channel in the guild/server.
            '''
            # username = str(msg.author)
            usr_msg = str(msg.content)
            channel = str(msg.channel)

            ############################## Checks for not doing anything ##############################

            # don't respond to yourself
            if msg.author == self.client.user:
                return 

            # only respond if usr sends a msg in one of the allowed channels
            if channel not in self.allowed_channels:
                return

            ############################## Personal Assistant Channel ##############################
            if channel == self.personal_assistant_channel:
                await self.personal_assistant_block(msg, usr_msg)
                return

            ############################## Stable Diffusion ##############################
            if channel == self.stable_diffusion_channel:
                await self.sd_text2img(msg, usr_msg) # TODO: copy the input parameters formatting that midjourney uses
                return

            ############################## GPT X ##############################
            # if sent in GPT_CHANNEL, send back a GPTX response
            if channel == self.gpt3_channel_name:
                # catch if is a command
                if usr_msg[0] == self.cmd_prefix:
                    # pass to PA block without the prefix
                    await self.personal_assistant_block(msg, usr_msg[1:])
                    return

                # check to see if we are running out of tokens for current msg log
                # get the current thread length
                curr_thread = await self.get_curr_gpt_thread()
                curr_thread_len_in_tokens = len(curr_thread) / 4 # 1 token ~= 4 chars
                while curr_thread_len_in_tokens > int(self.gpt3_settings["max_tokens"][0]):
                    # remove the 2nd oldest message from the thread (first oldest is the prompt)
                    self.gpt3_settings["messages"][0].pop(1)
                
                # use usr_msg to generate new response from API
                gpt_response = await self.gen_gpt3(usr_msg)

                # reformat to put into messages list for future context, and save
                formatted_response = {"role":self.chatgpt_name, "content":gpt_response}
                self.gpt3_settings["messages"][0].append(formatted_response)

                # send the response to the user
                await self.send_msg_to_usr(msg, gpt_response)
                return

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    bot = BMO()
    bot.run_discord_bot()