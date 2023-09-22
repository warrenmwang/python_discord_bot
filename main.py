import discord
import asyncio
import os
import sys
import openai
import requests
import subprocess
import io, base64
from concurrent.futures import ThreadPoolExecutor
import pickle
import time
from PIL import Image
from dotenv import load_dotenv
import queue
load_dotenv()

# CONSTANTS
DISCORD_MSGLEN_CAP=2000

# GLOBAL FUNCTIONS (what could go wrong)
def run_bash(command : str) -> tuple[str,str]:
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = result.stdout
        stderr = result.stderr
        return stdout, stderr
    except Exception as e:
        return "", str(e)

async def send_msg_to_usr(msg : discord.message.Message, usr_msg : str) -> None: 
    '''
    in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
    the damn message (whether it be one or multiple messages)
    '''
    diff = len(usr_msg)
    start = 0
    end = DISCORD_MSGLEN_CAP
    while diff > 0:
        await msg.channel.send(usr_msg[start:end])
        start = end
        end += DISCORD_MSGLEN_CAP
        diff -= DISCORD_MSGLEN_CAP

async def send_img_to_usr(msg : discord.message.Message, imgPath : str) -> None:
    '''given the image path in the filesystem, send it to the author of the msg'''
    await msg.channel.send(file=discord.File(imgPath))

# Classes for functionalities
class StableDiffusion:
    def __init__(self):
        self.stable_diffusion_channel = os.getenv('STABLE_DIFFUSION_CHANNEL')
        self.stable_diffusion_output_dir = os.getenv('STABLE_DIFFUSION_OUTPUT_DIR')
        self.stable_diffusion_toggle = False
        self.cmd_prefix = "!"

    async def handle(self, msg : discord.message.Message, usr_msg : str) -> None:
        '''
        Entrance function into doing anything with stable diffusion.
        '''
        # cmd (help, status, on, off)
        if usr_msg[0] == self.cmd_prefix:
            usr_msg = usr_msg[1:].lower()
            if usr_msg == 'status':
                await send_msg_to_usr(msg, 'ON' if self.stable_diffusion_toggle else 'OFF')
            elif usr_msg == 'off' and self.stable_diffusion_toggle == False:
                await send_msg_to_usr(msg, 'Already off.')
            elif usr_msg == 'off' and self.stable_diffusion_toggle == True:
                await self.sd_unload_model() 
                await send_msg_to_usr(msg, "SD OFF.")
                self.stable_diffusion_toggle = False
            elif usr_msg == 'on' and self.stable_diffusion_toggle == True:
                await send_msg_to_usr(msg, 'Already on.')
            elif usr_msg == 'on' and self.stable_diffusion_toggle == False:
                await self.sd_load_model() 
                await send_msg_to_usr(msg, 'Turning on SD (wait like 5 seconds for it to load)...')
                self.stable_diffusion_toggle = True
            elif usr_msg == 'help':
                await send_msg_to_usr(msg, '!help - show this message\n!on - load model to GPU\n!off - unload model from GPU\n!status - display if model is loaded or not')
            else:
                await send_msg_to_usr(msg, 'use !help for help')
            return

        # input is a txt2img prompt
        if self.stable_diffusion_toggle: # note api is NOT loaded by default -- load/reload and unload manually
            await self.sd_txt2img(msg, usr_msg) # TODO: copy the input parameters formatting that midjourney uses
        else:
            await send_msg_to_usr(msg, "Stable Diffusion is not loaded. Load it by running !on (be sure you have enough VRAM).")

    
    async def sd_txt2img(self, msg : discord.message.Message, usr_msg : str) -> None:
        '''
        ping the localhost stablediffusion api 
        '''
        # these can be adjustable, tho need to figure out what they mean
        payload = {
                    "prompt": usr_msg,
                    # "enable_hr": False,
                    # "denoising_strength": 0,
                    # "firstphase_width": 0,
                    # "firstphase_height": 0,
                    # "hr_scale": 2,
                    # "hr_upscaler": "string",
                    # "hr_second_pass_steps": 0,
                    # "hr_resize_x": 0,
                    # "hr_resize_y": 0,
                    # "hr_sampler_name": "string",
                    # "hr_prompt": "",
                    # "hr_negative_prompt": "",
                    # "prompt": "",
                    # "styles": [
                    #     "string"
                    # ],
                    # "seed": -1,
                    # "subseed": -1,
                    # "subseed_strength": 0,
                    # "seed_resize_from_h": -1,
                    # "seed_resize_from_w": -1,
                    # "sampler_name": "Euler",
                    # "batch_size": 1,
                    "n_iter": 4,
                    "steps": 25,
                    "cfg_scale": 8.5,
                    "width": 768,
                    "height": 768,
                    # "restore_faces": False,
                    # "tiling": False,
                    # "do_not_save_samples": False,
                    # "do_not_save_grid": False,
                    # "negative_prompt": "string",
                    # "eta": 0,
                    # "s_min_uncond": 0,
                    # "s_churn": 0,
                    # "s_tmax": 0,
                    # "s_tmin": 0,
                    # "s_noise": 1,
                    # "override_settings": {},
                    # "override_settings_restore_afterwards": True,
                    # "script_args": [],
                    # "sampler_index": "Euler",
                    # "script_name": "string",
                    # "send_images": True,
                    # "save_images": False,
                    # "alwayson_scripts": {}
                }

        await send_msg_to_usr(msg, f"Creating image of \"{usr_msg}\"")

        response = requests.post(url=f'http://127.0.0.1:7860/sdapi/v1/txt2img', json=payload)
        r = response.json()
        # DEBUG
        # print(r.keys())
        # for k in r.keys():
        #     print(f'{r[k]=}')

        # TODO: use PIL to manually make a grid of the 4 images into a single image to be return to the user.
        for i in r['images']:
            image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
            image.save(self.stable_diffusion_output_dir)
            await send_img_to_usr(msg, self.stable_diffusion_output_dir)

    async def sd_load_model(self):
        '''
        load the model onto the gpu with the REST API params
        '''
        cmd = 'tmux new-session -d -s sd_api && tmux send-keys -t sd_api "cd stable-diffusion-webui && ./webui.sh --xformers --disable-safe-unpickl --api" C-m'
        run_bash(cmd)

    async def sd_unload_model(self):
        '''
        unload the model
        '''
        cmd = 'tmux kill-session -t sd_api'
        run_bash(cmd)

class ChatGPT:
    def __init__(self):
        # TODO:
        pass

# main class
class BMO:
    '''
    BMO is our general virtual assistant.
    BMO does a lot of things: helps you talk to a smart LLM (GPT), handle basic daily life stuff (reminders, TODO: drafts emails, cheers for you in the fight for life),
    creates images for you (StableDiffusion) and more!...
    '''
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
        self.chatgpt_name="assistant"
        self.gpt3_model_to_max_tokens = {
            "gpt-3.5-turbo": 4096,
            "gpt-4": 8192,
            "gpt-4-32k": 32768
        }
        self.cmd_prefix = "!"

        # stable diffusion
        self.StableDiffusion = StableDiffusion()
        self.stable_diffusion_channel = self.StableDiffusion.stable_diffusion_channel

        # personal assistant
        self.personal_assistant_channel = os.getenv('PERSONAL_ASSISTANT_CHANNEL')
        self.personal_assistant_state = None
        self.personal_assistant_modify_prompts_state = None
        self.personal_assistant_modify_prompts_buff = []
        self.personal_assistant_commands = {
            "general": {
                "help": "show this message",
                "pa_llama": "toggle the use of a llama model to interpret an unknown command (huge WIP)",
                "pa_gpt": "toggle the use of ChatGPT to interpret an unknown command",
                "remind me": "format is `[remind me], [description], [numerical value], [time unit (s,m,h)]`; sets a reminder that will ping you in a specified amount of time",
                'shakespeare': 'generate a random snippet of shakespeare'
            },
            "chatgpt": {
                "convo len" : 'show current gpt3 context length',
                "reset thread" : 'reset gpt3 context length',
                "show thread" : 'show the entire current convo context',
                "gptsettings" : 'show the current gpt3 settings',
                # "gptreplsettings" : 'show gpt3 repl settings',
                "gptset": "format is `gptset, [setting_name], [new_value]` modify gpt3 settings",
                # "gptreplset": "format is `gptreplset, [setting_name], [new_value]` modify gpt3 repl settings",
                "curr prompt": "get the current prompt name",
                "change prompt, [new prompt]": "change prompt to the specified prompt(NOTE: resets entire message thread)",
                "show prompts": "show the available prompts for gpt3",
                "list models": "list the available gpt models",
                "modify prompts": "modify the prompts for gpt",
                "save thread": "save the current gptX thread to a file",
                "show old threads": "show the old threads that have been saved",
                "load thread": "format is `load thread, [unique id]` load a gptX thread from a file",
                "delete thread": "format is `delete thread, [unique id]` delete a gptX thread from a file",
                "current model": "show the current gpt model",
                "swap": "swap between gpt3.5 and gpt4 (regular)",
            },
        }
        self.personal_assistant_command_options = [c for _, v in self.personal_assistant_commands.items() for c in list(v.keys())]
        help_str = ''
        sections = list(self.personal_assistant_commands.keys())
        for section in sections:
            help_str += f"{section.upper()}\n"
            for k,v in self.personal_assistant_commands[section].items():
                help_str += f"\t{k} - {v}\n"
        self.help_str = help_str

        self.llama_pa_prompt = f"You are a virtual assistant agent discord bot. The available commands are {self.personal_assistant_commands}. Help the user figure out what they want to do. The following is the conversation where the user enters the unknown command. Output a one sentence response."
        self.llama_pa_toggle = False
        self.gpt_pa_prompt = f"You are a virtual assistant, бог, and the user has entered an unrecognized command. The commands that you do know are {self.personal_assistant_commands}. Help the user figure out what they want to do. You are benevolent and nice."
        self.gpt_pa_toggle = True # enable GPT help by default

        self.pa_context_queue = queue.Queue() # if empty, know that there is no current context going on TODO: use this to have more advanced talks with GPT to interact with the hard coded functionalities

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
        await send_msg_to_usr(msg, "".join([f"{key} ({gpt3_settings[key][1]}) = {gpt3_settings[key][0]}\n" for key in gpt3_settings.keys() if key != "messages"]))

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
        
    ############################## GPT3 ##############################

    ############################## local llm stuff ###############################
    async def local_gpt_shakespeare(self, length : int)->str:
        '''
        generates a random shakespeare snippet from a local GPT trained on shakespeare
        from nanoGPT repo

        cut the generation output to be of the input length 

        this is duct-taped together im sorry
        '''
        stdout, stderr = run_bash(f'cd nanoGPT && /home/wang/anaconda3/envs/dev2-py310/bin/python sample.py --out_dir=../ml_weights/shakespeare --max_new_tokens={length}')
        if len(stderr) != 0:
            return f"generation failed -> {stderr}"
        else:
            stdout = stdout.split("\n\n")
            return '\n\n'.join(stdout[1:])

    async def local_gpt_llama(self, usr_str:str)->str:
        '''
        given the user str help the user figure out what they want to do by using a local llama program to figure it out
        no chatgpt here...(this is pretty bad tho if im only using 7B)
        '''
        input_ = f"{self.llama_pa_prompt}\n\nUser: {usr_str}\nAgent:"
        # cmd = f'cd llama.cpp && ./main -m ./models/llama-2/13B/ggml-model-q4_0.gguf -n 128 -p "{input_}" -e'
        cmd = f'cd llama.cpp && ./main -m ./models/7B/ggml-model-q4_0.gguf -n 128 -p "{input_}" -e'
        stdout, _ = run_bash(cmd)
        ret = stdout.split("Agent:")[1]
        return ret
    ############################## local llm stuff ###############################

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
                await send_msg_to_usr(msg, "Ok, cancelling.")
                return

            # Stage 1: usr picks a operator
            if self.personal_assistant_modify_prompts_state == "asked what to do":
                # check response
                if usr_msg == "edit":
                    self.personal_assistant_modify_prompts_state = "edit"
                    await send_msg_to_usr(msg, "Ok which prompt would you like to edit? [enter prompt name]")
                    return
                elif usr_msg == "add":
                    self.personal_assistant_modify_prompts_state = "add"
                    await send_msg_to_usr(msg, "Ok, write a prompt in this format: [name]<SEP>[PROMPT] w/o the square brackets.")
                    return
                elif usr_msg == "delete":
                    self.personal_assistant_modify_prompts_state = "delete"
                    await send_msg_to_usr(msg, "Ok, which prompt would you like to delete? [enter prompt name]")
                    return
                elif usr_msg == "changename":
                    self.personal_assistant_modify_prompts_state = "changename"
                    await send_msg_to_usr(msg, "Ok, which prompt name would you like to rename? [enter prompt name]")
                    return
                else:
                    await send_msg_to_usr(msg, "Invalid response, please try again.")
                    return

            # Stage 2: usr provides more info for an already chosen operator
            if self.personal_assistant_modify_prompts_state == "edit":
                await send_msg_to_usr(msg, f"Ok, you said to edit {usr_msg}.\nSend me the new prompt for this prompt name. (just the new prompt in its entirety)")
                self.personal_assistant_modify_prompts_buff.append(usr_msg)
                self.personal_assistant_modify_prompts_state = "edit2"
                return
            if self.personal_assistant_modify_prompts_state == "edit2":
                # update our mapping of prompt name to prompt dict, then write the new prompts to file
                prompt_name = self.personal_assistant_modify_prompts_buff.pop()
                new_prompt = usr_msg
                self.map_promptname_to_prompt[prompt_name] = new_prompt
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await send_msg_to_usr(msg, f"Updated '{prompt_name}' to '{new_prompt}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
            if self.personal_assistant_modify_prompts_state == "add":
                await send_msg_to_usr(msg, f"Ok, you said to add '{usr_msg}'...")
                prompt_name = usr_msg.split("<SEP>")[0]
                prompt = usr_msg.split("<SEP>")[1]
                self.map_promptname_to_prompt[prompt_name] = prompt
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await send_msg_to_usr(msg, f"Added '{prompt_name}' with prompt '{prompt}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
            if self.personal_assistant_modify_prompts_state == "delete":
                await send_msg_to_usr(msg, f"Ok, you said to delete '{usr_msg}'...")
                prompt_name = usr_msg
                del self.map_promptname_to_prompt[prompt_name]
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await send_msg_to_usr(msg, f"Deleted '{prompt_name}'")
                self.personal_assistant_state = None
                self.personal_assistant_modify_prompts_state = None
                return
            if self.personal_assistant_modify_prompts_state == "changename":
                self.personal_assistant_modify_prompts_buff.append(usr_msg)
                self.personal_assistant_modify_prompts_state = "changename2"
                await send_msg_to_usr(msg, f"Ok, what would you like to change the {usr_msg} to?")
                return
            if self.personal_assistant_modify_prompts_state == "changename2":
                prompt_name = self.personal_assistant_modify_prompts_buff.pop()
                new_prompt_name = usr_msg
                prompt = self.map_promptname_to_prompt[prompt_name]
                del self.map_promptname_to_prompt[prompt_name]
                self.map_promptname_to_prompt[new_prompt_name] = prompt
                self.gpt_save_prompts_to_file() # write the new prompts to file
                await send_msg_to_usr(msg, f"Changed '{prompt_name}' to '{new_prompt_name}'")
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

        # all commands below this are not case sensitive to the usr_msg so just lowercase it
        usr_msg = usr_msg.lower()

        # convert shortcut to full command if present
        usr_msg = _pa_shortcut_cmd_convertor(usr_msg)

        # check if user input is a hard-coded command
        cmd = usr_msg.split(",")[0]
        if cmd not in self.personal_assistant_command_options:
            if self.llama_pa_toggle:
                await send_msg_to_usr(msg, "Not a hard coded command, letting LLAMA interpret...")
                await send_msg_to_usr(msg, await self.local_gpt_llama(usr_msg))
            elif self.gpt_pa_toggle:
                await send_msg_to_usr(msg, "Not a hard coded command, letting GPT interpret...")
                d = { # TODO: make these params adjustable?
                    "model": ["gpt-3.5-turbo", "str"],
                    "messages" : [[{"role":self.chatgpt_name, "content":self.gpt_pa_prompt}], "list of dicts"],
                    "temperature": ["0.0", "float"],
                    "top_p": ["1.0", "float"],
                    "frequency_penalty": ["0", "float"],
                    "presence_penalty": ["0", "float"],
                    "max_tokens": ["4096", "int"],
                }
                response = await self.gen_gpt3(usr_msg, d)
                await send_msg_to_usr(msg, response)
            else:
                await send_msg_to_usr(msg, 'Unknown command, run `help`.')
            return

        # Allow using GPT3 to interpret unknown commands as well...
        # it's just smarter than the small llama's I have now
        if usr_msg == "pa_gpt":
            self.gpt_pa_toggle = True
            self.llama_pa_toggle = False
            await send_msg_to_usr(msg, 'GPT interpret selected.')
            return
        
        # toggle llama interpretting wrong commands
        if usr_msg == "pa_llama":
            self.llama_pa_toggle = True
            self.gpt_pa_toggle = False
            await send_msg_to_usr(msg, 'LLama interpret selected.')
            return

        # list all the commands available
        if usr_msg == "help":
            await msg.channel.send(self.help_str)
            return

        # testing out nanoGPT integration
        if usr_msg == "shakespeare":
            await send_msg_to_usr(msg, "Generating...")
            await send_msg_to_usr(msg, await self.local_gpt_shakespeare(length=100))
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
            await send_msg_to_usr(msg, f"Saved thread to file as {curr_time}.pkl")
            return

        # show old threads that have been saved
        if usr_msg == "show old threads":
            # for now, list all the threads...
            for filename in os.listdir("./pickled_threads"):
                # read the file and unpickle it
                with open(f"./pickled_threads/{filename}", "rb") as f:
                    msgs_to_load = pickle.load(f)
                    await send_msg_to_usr(msg, f"Thread id: {filename}")
                    for tmp in msgs_to_load:
                        tmp_role = tmp["role"]
                        tmp_msg = tmp["content"]
                        await send_msg_to_usr(msg, f"###{tmp_role.capitalize()}###\n{tmp_msg}\n###################\n")
            return

        # load msg log from file
        if usr_msg[:11] == "load thread":
            thread_id = usr_msg.split(",")[1].strip()

            if len(thread_id) == 0:
                await send_msg_to_usr(msg, "No thread id specified")
                return

            if thread_id[-4:] == ".pkl":
                thread_id = thread_id[:-4]

            # read the file and unpickle it
            with open(f"./pickled_threads/{thread_id}.pkl", "rb") as f:
                msgs_to_load = pickle.load(f)
                # set the current gptsettings messages to this 
                self.gpt3_settings["messages"][0] = msgs_to_load
            await send_msg_to_usr(msg, f"Loaded thread {thread_id}.pkl") 
            return
        
        # delete a saved thread
        if usr_msg[:13] == "delete thread":
            thread_id = usr_msg.split(",")[1].strip()

            if len(thread_id) == 0:
                await send_msg_to_usr(msg, "No thread id specified")
                return

            # delete the file
            os.remove(f"./pickled_threads/{thread_id}.pkl")
            await send_msg_to_usr(msg, f"Deleted thread {thread_id}.pkl")
            return

        # list available models of interest
        if usr_msg == "list models":
            tmp = "".join([f"{k}: {v}\n" for k,v in self.gpt3_model_to_max_tokens.items()])
            await send_msg_to_usr(msg, f"Available models:\n{tmp}")
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
                await send_msg_to_usr(msg, f"These are the existing prompts:\n{self.get_all_gpt_prompts_as_str()}\nDo you want to edit an existing prompt, add a new prompt, delete a prompt, or change a prompt's name? (edit/add/delete/changename)")
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
            await send_msg_to_usr(msg, self.get_all_gpt_prompts_as_str())
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
            # await send_msg_to_usr(msg, curr_thread)
            for tmp in self.gpt3_settings["messages"][0]:
                tmp_role = tmp["role"]
                tmp_msg = tmp["content"]
                await send_msg_to_usr(msg, f"###{tmp_role.capitalize()}###\n{tmp_msg}\n###################\n")
            return

        # reset the current convo with the curr prompt context
        if usr_msg == "reset thread":
            await self.gpt_context_reset()
            await msg.channel.send(f"Thread Reset. {await _pa_get_curr_convo_len_and_approx_tokens(self)}")
            return
        
        # check curr convo context length
        if usr_msg == "convo len":
            await send_msg_to_usr(msg, await _pa_get_curr_convo_len_and_approx_tokens(self))
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

                await send_msg_to_usr(msg, f"Reminder set for '{task}' in {time} {unit}.")
                await asyncio.sleep(remind_time)
                await send_msg_to_usr(msg, f"REMINDER: {task}")
            except Exception as e:
                await send_msg_to_usr(msg, "usage: remind me, [task_description], [time], [unit]")
            return

    ############################## Personal Assistant ##############################


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
            # gpt init
            await self.gpt_prompt_initializer()
            openai.api_key = self.GPT3_OPENAI_API_KEY

            # bot is a go!
            print(f'{self.client.user} running!')

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
                await self.StableDiffusion.handle(msg, usr_msg)
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
                await send_msg_to_usr(msg, gpt_response)
                return

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    bot = BMO()
    bot.run_discord_bot()