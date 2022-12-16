import discord
from discord.ext import tasks
import asyncio
import random
from datetime import datetime
import os
import openai
from dotenv import load_dotenv
import subprocess
import urllib.request

from gpt3_repl import answer_one_question_step_one, answer_one_question_step_two, GPT3_REPL_SETTINGS

# give calculator more advanced math capabilities
import numpy as np

# web scraping stuff
import requests, bs4

load_dotenv()

############################## GLOBAL VARS ##############################
TOKEN = os.getenv('DISCORD_TOKEN')
PHOTOS_DIR = os.getenv('PHOTOS_DIR')

STABLE_DIFFUSION_CHANNEL_NAME_1 = os.getenv('STABLE_DIFFUSION_CHANNEL_NAME_1')
STABLE_DIFFUSION_CHANNEL_NAME_2 = os.getenv('STABLE_DIFFUSION_CHANNEL_NAME_2')
STABLE_DIFFUSION_PYTHON_BIN_PATH = os.getenv('STABLE_DIFFUSION_PYTHON_BIN_PATH')
STABLE_DIFFUSION_SCRIPT_PATH = os.getenv('STABLE_DIFFUSION_SCRIPT_PATH')
STABLE_DIFFUSION_ARGS_1 = os.getenv('STABLE_DIFFUSION_ARGS_1')
STABLE_DIFFUSION_ARGS_2 = os.getenv('STABLE_DIFFUSION_ARGS_2')
STABLE_DIFFUSION_OUTPUT_DIR = os.getenv('STABLE_DIFFUSION_OUTPUT_DIR')

MY_NAME = os.getenv('MY_NAME')
MY_DREAM = os.getenv('MY_DREAM')
MY_CURRENT_LOCATION = os.getenv('MY_CURRENT_LOCATION')

# different api keys
GPT3_OPENAI_API_KEY = os.getenv("GPT3_OPENAI_API_KEY")
CODEX_OPENAI_API_KEY = os.getenv("CODEX_OPENAI_API_KEY")

GPT3_CHANNEL_NAME = os.getenv('GPT3_CHANNEL_NAME')
GPT3_CHANNEL_ID = os.getenv('GPT3_CHANNEL_ID')
GPT3_SETTINGS = {
    "engine": ["text-davinci-003", "str"],
    "temperature": ["0.0", "float"],
    "max_tokens": ["2000", "int"],
    "top_p": ["1.0", "float"],
    "frequency_penalty": ["0", "float"],
    "presence_penalty": ["0", "float"],
    "chatbot_roleplay": ["T", "str"],
    "stop" : [["\n\nINPUT:"], "list of strings"]
}

DAILY_REMINDERS_SWITCH = True
PERSONAL_ASSISTANT_CHANNEL = os.getenv('PERSONAL_ASSISTANT_CHANNEL')
GPT3_REPL_CHANNEL_NAME = os.getenv("GPT3_REPL_CHANNEL_NAME")
GPT3_REPL_WORKING_PROMPT_FILENAME = os.getenv("GPT3_REPL_WORKING_PROMPT_FILENAME")
GPT3_REPL_WAITING_ON_CODE_CONFIRMATION = False
GPT3_REPL_SCRIPT_FILENAME = os.getenv("GPT3_REPL_SCRIPT_FILENAME")

# we can have multiple GPT3 convo contexts, init with the roleplay one
GPT3_PROMPT_PERSONAL_ASSISTANT_FILE=os.getenv("GPT3_PROMPT_PERSONAL_ASSISTANT_FILE")
GPT3_PROMPT_ROLEPLAY_FILE=os.getenv("GPT3_PROMPT_ROLEPLAY_FILE")

ALL_GPT3_AVAILABLE_PROMPTS = ["Roleplay", "Personal Assistant"]
MAP_PROMPT_TO_PROMPTFILE = {
    "Roleplay" : GPT3_PROMPT_ROLEPLAY_FILE,
    "Personal Assistant": GPT3_PROMPT_PERSONAL_ASSISTANT_FILE
}
CURR_PROMPT = "Roleplay"
CURR_CONVO_CONTEXT_LEN_MAX = int(GPT3_SETTINGS["max_tokens"][0]) * 2 # init w/ double max_tokens length
CURR_CONVO_CONTEXT = None
ALLOWED_CHANNELS = [GPT3_CHANNEL_NAME, STABLE_DIFFUSION_CHANNEL_NAME_1, STABLE_DIFFUSION_CHANNEL_NAME_2, PERSONAL_ASSISTANT_CHANNEL, GPT3_REPL_CHANNEL_NAME]

############################## STABLE DIFFUSION ##############################

async def gen_stable_diffusion(msg, usr_msg, chnl_num):
    '''
    takes in usr_msg as the prompt (and generation params, don't need to include outdir, automatically added)
    and generate image(s) using stablediffusion, then send them back to the user
    '''
    # first generate image(s)
    prompt_file = f"{STABLE_DIFFUSION_OUTPUT_DIR}/prompt_file.txt"
    with open(prompt_file, "w") as f:
        f.write(f"{usr_msg} --outdir {STABLE_DIFFUSION_OUTPUT_DIR}")
        f.write('\n')

    if chnl_num == 1:
        cmd = f"{STABLE_DIFFUSION_PYTHON_BIN_PATH} {STABLE_DIFFUSION_SCRIPT_PATH} {STABLE_DIFFUSION_ARGS_1} {prompt_file}"
    else:
        cmd = f"{STABLE_DIFFUSION_PYTHON_BIN_PATH} {STABLE_DIFFUSION_SCRIPT_PATH} {STABLE_DIFFUSION_ARGS_2} {prompt_file}"

    try:
        subprocess.run(cmd, shell=True)
    except Exception as e:
        await msg.channel.send(f"StableDiffusion: got error on subprocess: {e}")
        return

    # get generated image(s), if any
    imgs_to_send = []
    for file in os.listdir(STABLE_DIFFUSION_OUTPUT_DIR):
        file_path = os.path.join(STABLE_DIFFUSION_OUTPUT_DIR, file)
        if file_path[-4:] == ".png":
            imgs_to_send.append(file_path)
    # if no images were generated, send notify usr
    if len(imgs_to_send) == 0:
        await msg.channel.send(f"StableDiffusion: no images generated (probably CUDA out of memory)")
    else:
        # have images, send them
        for img in imgs_to_send:
            await msg.channel.send(file=discord.File(img))

    # delete all files in outputdir
    for file in os.listdir(STABLE_DIFFUSION_OUTPUT_DIR):
        file_path = os.path.join(STABLE_DIFFUSION_OUTPUT_DIR, file)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            await msg.channel.send("something went wrong in cleanup procedure in stable diffusion")

############################## GPT 3 ##############################

async def gen_gpt3_repl_step_one(usr_msg : str) -> str:
    '''
    1. try to answer the question immediately
    2. if cannot, then generate python code and send that to user
    3. then need to await confirmation to run the code or not (go to step 2 function)


    receives a str prompt that should be passed into a gpt3 generation under the context
    that GPT3 is serving as a repl that generates code if needed and provides an answer
    '''
    openai.api_key = CODEX_OPENAI_API_KEY
    if (answer_one_question_step_one(usr_msg) == 1):
        # direct answer is available
        with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "r") as f:
            tmp = f.readlines()
            answer = tmp[-1] # get answer (expect one line answers for now)
        os.unlink(GPT3_REPL_WORKING_PROMPT_FILENAME) # cleanup by deleting the working prompt file
        return answer
    else:
        # show to user the python script generated, ask for confirmation before running code
        ret_str = f"This is the full script:\n==========\n"
        with open(GPT3_REPL_SCRIPT_FILENAME, "r") as f:
            ret_str += f.read()
        ret_str += "==========\nDoes this look ok to run? [y/n]"
        return ret_str

async def gen_gpt3_repl_step_two(usr_msg: str) -> str:
    '''
    usr_msg should be either [y/n]

    if y run python script and return the answer
    if n abort and cleanup

    give all this work to the func
    '''
    ret_str = answer_one_question_step_two(usr_msg)
    return ret_str


async def gen_gpt3(usr_msg : str, settings_dict: dict = GPT3_SETTINGS) -> str:
    '''
    retrieves a GPT3 response given a string input and a dictionary containing the settings to use
    returns the response str
    '''
    openai.api_key = GPT3_OPENAI_API_KEY
    response = openai.Completion.create(
        engine = settings_dict["engine"][0],
        prompt = usr_msg,
        temperature = float(settings_dict["temperature"][0]),
        max_tokens = int(settings_dict["max_tokens"][0]),
        top_p = float(settings_dict["top_p"][0]),
        frequency_penalty = float(settings_dict["frequency_penalty"][0]),
        presence_penalty = float(settings_dict["presence_penalty"][0]),
        stop = settings_dict["stop"][0]
    )
    return response.choices[0].text

async def gptsettings(msg : discord.message.Message, GPT3_SETTINGS : dict) -> None:
    '''
    prints out all available gpt3 settings, their current values, and their data types
    '''
    await msg.channel.send("".join([f"{key} ({GPT3_SETTINGS[key][1]}) = {GPT3_SETTINGS[key][0]}\n" for key in GPT3_SETTINGS.keys()]))

async def gptset(usr_msg : str, GPT3_SETTINGS : dict) -> None:
    '''
    original call is:
        GPTSET [setting_name] [new_value]

    sets the specified gpt3 parameter to the new value
    '''
    tmp = usr_msg.split()
    setting, new_val = tmp[1], tmp[2]
    GPT3_SETTINGS[setting][0] = new_val # always gonna store str

async def gpt_context_reset() -> None:
    global CURR_CONVO_CONTEXT
    global CURR_PROMPT
    CURR_CONVO_CONTEXT = update_gpt3_convo_prompt(CURR_PROMPT)

def update_gpt3_convo_prompt(CURR_PROMPT : str) -> str:
    '''
    given the current prompt, return the convo context
    CURR_PROMPT -> filename -> read contents -> return contents
    '''
    global MAP_PROMPT_TO_PROMPTFILE
    file = MAP_PROMPT_TO_PROMPTFILE[CURR_PROMPT]
    with open(file, "r") as f:
        return f.read()


############################## Personal Assistant ##############################

async def get_weather_data(location: str) -> str:
    '''
    input: location (str) -- website url with weather data at a location presearched
    output: str with whatever formatting that will be sent as a message directly
    '''
    res = requests.get(location)
    try:
        res.raise_for_status
    except Exception as e:
        return "Request to website failed."
    soup = bs4.BeautifulSoup(res.text, features="html.parser")
    ret_str = soup.select(".myforecast-current-lrg")[0].getText()
    return ret_str

async def personal_assistant_block(msg : discord.message.Message, usr_msg: str) -> None:
    '''
    Custom commands that do a particular hard-coded thing.
    '''
    global CURR_CONVO_CONTEXT_LEN_MAX
    global DAILY_REMINDERS_SWITCH
    global CURR_PROMPT
    global ALL_GPT3_AVAILABLE_PROMPTS
    global CURR_CONVO_CONTEXT

    usr_msg = usr_msg.lower()

    # list all the commands available
    if usr_msg == "help":
        help_str = \
        "List of available commands:\n\
        help: show this message\n\
        ip: show ip of computer running this bot\n\
        weather: show weather at location of computer\n\
        calc: use python eval() function\n\
        remind me: reminders\n\
        time: print time\n\
        daily reminders: show current status of daily reminders\n\
        daily reminders toggle: toggle the daily reminders\n\nGPT Settings:\n\n\
        convo len: show current gpt3 context length\n\
        convo max len: show current max convo len\n\
        change convo max len, [new_len]: change convo max len to new_len\n\
        reset thread: reset gpt3 context length\n\
        show thread: show the entire current convo context\n\
        gptsettings: show the current gpt3 settings\n\
        gptreplsettings: show gpt3 repl settings\n\
        gptset [setting_name] [new_value]: modify gpt3 settings\n\
        gptreplset [setting_name] [new_value]: modify gpt3 repl settings\n\
        prompt: get the current prompt context\n\
        change prompt, [new prompt]: change prompt to the specified prompt\n\
        show prompts: show the available prompts for gpt3\n\
        "
        await msg.channel.send(help_str)
        return
    
    # show the current gpt3 prompt
    if usr_msg == "prompt":
        await msg.channel.send(CURR_PROMPT)
        return

    # change gpt3 prompt
    if usr_msg[:13] == "change prompt":
        # accept only the index number of the new prompt
        try:
            x = list(map(str.strip, usr_msg.split(',')))
            new_ind = int(x[1])
            new_prompt = ALL_GPT3_AVAILABLE_PROMPTS[new_ind]
            CURR_PROMPT = new_prompt
            # update the current context for the prompt given
            CURR_CONVO_CONTEXT = update_gpt3_convo_prompt(CURR_PROMPT)
            await msg.channel.send("New current prompt set to: " + new_prompt)
            return
        except Exception as e:
            await msg.channel.send("usage: change prompt, [new prompt]")
            return

    # show available prompts as (ind. prompt)
    if usr_msg == "show prompts":
        x = "".join([f"{i}. {x}\n" for i, x in enumerate(ALL_GPT3_AVAILABLE_PROMPTS)])
        await msg.channel.send(x) 
        return 

    if usr_msg == "daily reminders":
        x = "ON" if DAILY_REMINDERS_SWITCH else "OFF"
        await msg.channel.send(x)
        return

    if usr_msg == "daily reminders toggle":
        DAILY_REMINDERS_SWITCH = False if DAILY_REMINDERS_SWITCH else True
        await msg.channel.send(f"Set to: {'ON' if DAILY_REMINDERS_SWITCH else 'OFF'}")
        return

    # gpt3 repl settings
    if usr_msg == "gptreplsettings":
        await gptsettings(msg, GPT3_REPL_SETTINGS)
        return

    # show user current GPT3 settings
    if usr_msg == "gptsettings":
        await gptsettings(msg, GPT3_SETTINGS)
        return

    # user wants to modify GPT3 settings
    if usr_msg[0:6] == "gptset":
        ''' expect format: gptset [setting_name] [new_value]'''
        try:
            await gptset(usr_msg, GPT3_SETTINGS)
            await msg.channel.send("New parameter saved, current settings:")
            await gptsettings(msg, GPT3_SETTINGS)
        except Exception as e:
            await msg.channel.send("gptset: gptset [setting_name] [new_value]")
        return
    
    # modify GPT3repl settings
    if usr_msg[:10] == "gptreplset":
        ''' expect format: gptreplset [setting_name] [new_value]'''
        try:
            await gptset(usr_msg, GPT3_REPL_SETTINGS)
            await msg.channel.send("New parameter saved, current settings:")
            await gptsettings(msg, GPT3_REPL_SETTINGS)
        except Exception as e:
            await msg.channel.send("gptset: gptset [setting_name] [new_value]")
        return
    
    # show the current thread
    if usr_msg == "show thread":
        # discord caps at 2000 chars per message body
        x = CURR_CONVO_CONTEXT[-2000:] if len(CURR_CONVO_CONTEXT) > 2000 else CURR_CONVO_CONTEXT
        await msg.channel.send(x)
        return

    # reset the current convo with the curr prompt context
    if usr_msg == "reset thread":
        await gpt_context_reset()
        await msg.channel.send(f"Thread Reset. Starting with (prompt) convo len = {len(CURR_CONVO_CONTEXT)}")
        return
    
    # max convo len
    if usr_msg == "convo max len":
        await msg.channel.send(CURR_CONVO_CONTEXT_LEN_MAX) 
        return

    # idk if im going to use this function, but I'm going to write it
    if usr_msg[:20] == "change convo max len":
        try:
            tmp = list(map(str.strip, usr_msg.split(',')))
            tmp1 = tmp[1]
            CURR_CONVO_CONTEXT_LEN_MAX = int(tmp1) 
            await msg.channel.send(f"New convo max len = {CURR_CONVO_CONTEXT_LEN_MAX}")
            return
        except Exception as e:
            await msg.channel.send("usage: change convo max len, [new_len]")
            return
        
    # check curr convo context length
    if usr_msg == "convo len":
        await msg.channel.send(len(CURR_CONVO_CONTEXT))
        return

	# return the current computer ip addr
    if usr_msg == "ip":
        await msg.channel.send(urllib.request.urlopen('https://ident.me').read().decode('utf8'))
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
            else:
                remind_time = -1
                
            if remind_time == -1:
                # unclear units (maybe add days ?)
                await msg.channel.send("only time units implemented: s, m, h")
                return

            await msg.channel.send("Reminder set.")
            await asyncio.sleep(remind_time)
            await msg.channel.send(f"REMINDER: {task}")
        except Exception as e:
            await msg.channel.send("usage: remind me, [task_description], [time], [unit]")
        return

    # Weather (location default get from env)
    if usr_msg == "weather":
        await msg.channel.send(await get_weather_data(MY_CURRENT_LOCATION))
        return

    # Calculator
    # NOTE: this is dangerous if input is untrusted, can be used to run arbitrary python and shell code
    # this is personal project, so I'm fine with this
    if usr_msg[0:5] == 'calc:':
        try:
            tmp = usr_msg.split(":")
            await msg.channel.send(eval(tmp[1]))
        except Exception as e:
            await msg.channel.send("usage: calc: [math exp in python (available libraries include: numpy)]")
        return

    # Time
    if usr_msg[0:5] == 'time':
        tmp = str(datetime.now()).split()
        date, time_24_hr = tmp[0], tmp[1]
        await msg.channel.send(f"Date: {date}\nTime 24H: {time_24_hr}")
        return

    await msg.channel.send("That command was not found.")

############################## Main Function ##############################

def run_discord_bot():
    '''
    Main loop
    '''
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    global DAILY_REMINDERS_SWITCH

    @tasks.loop(seconds = 30)
    async def msgs_on_loop():
        if DAILY_REMINDERS_SWITCH:
            hr_min_secs = str(datetime.now()).split()[1].split(':')
            msgs_on_loop_channel = client.get_channel(int(GPT3_CHANNEL_ID))
            msgs_on_loop_gpt_settings = {
                    "engine": ["text-davinci-002", "str"],
                    "temperature": ["0.7", "float"],
                    "max_tokens": ["200", "int"],
                    "top_p": ["1.0", "float"],
                    "frequency_penalty": ["0", "float"],
                    "presence_penalty": ["0", "float"],
                    "stop": [["INPUT:"], "list of strings"] # not used here, but need for function
                }

            # send a good morning msg at 7:00am
            if hr_min_secs[0] == '07' and hr_min_secs[1] == '00':
                prompt = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} You generate an inspirational quote for {MY_NAME}:"
                msg = await gen_gpt3(prompt, msgs_on_loop_gpt_settings)
                await msgs_on_loop_channel.send(msg)
                #img_name = random.choice(os.listdir(PHOTOS_DIR))
                #img_full_path = f"{PHOTOS_DIR}/{img_name}"
                #await msgs_on_loop_channel.send(file=discord.File(img_full_path))
                await asyncio.sleep(60)

            # send a lunchtime reminder msg at 12:00pm
            if hr_min_secs[0] == '12' and hr_min_secs[1] == '00':
                prompt = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} You send a text message reminding {MY_NAME} to eat lunch!:"
                await msgs_on_loop_channel.send(await gen_gpt3(prompt, msgs_on_loop_gpt_settings))
                await asyncio.sleep(60)

            # send a you can do it msg at 3:00pm
            if hr_min_secs[0] == '15' and hr_min_secs[1] == '00':
                prompt = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} You send a text message reminding {MY_NAME} that his dream of '{MY_DREAM}' will come true!:"
                await msgs_on_loop_channel.send(await gen_gpt3(prompt, msgs_on_loop_gpt_settings))
                await asyncio.sleep(60)

            # send a dinnertime reminder msg at 7:00pm
            if hr_min_secs[0] == '19' and hr_min_secs[1] == '00':
                prompt = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} You send a text message reminding {MY_NAME} to eat dinner!:"
                await msgs_on_loop_channel.send(await gen_gpt3(prompt, msgs_on_loop_gpt_settings))
                await asyncio.sleep(60)

            # send a get sleep reminder msg at 12:00am
            if hr_min_secs[0] == '00' and hr_min_secs[1] == '00':
                prompt = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} You send a text message reminding {MY_NAME} to go to sleep!:"
                await msgs_on_loop_channel.send(await gen_gpt3(prompt, msgs_on_loop_gpt_settings))
                await asyncio.sleep(60)

    ########################### INIT ############################
    @client.event
    async def on_ready():
        '''
        When ready, load all looping functions if any.
        '''
        print(f'{client.user} running!')
        global CURR_CONVO_CONTEXT
        CURR_CONVO_CONTEXT = update_gpt3_convo_prompt(CURR_PROMPT) # init it with the beginning roleplay info

        msgs_on_loop.start()
    ########################### INIT ############################

    @client.event
    async def on_message(msg : discord.message.Message):
        '''
        Entrance function for any message sent to any channel in the guild/server.
        '''
        # username = str(msg.author)
        usr_msg = str(msg.content)
        channel = str(msg.channel)

        ############################## Checks for not doing anything ##############################

        # don't respond to yourself
        if msg.author == client.user:
            return 

        # only respond if usr sends a msg in one of the allowed channels
        if channel not in ALLOWED_CHANNELS:
            return

        ############################## Personal Assistant Channel ##############################
        if channel == PERSONAL_ASSISTANT_CHANNEL:
            await personal_assistant_block(msg, usr_msg)
            return

        ############################## StableDiffusion ##############################

        # enable stablediffusion if you have a gpu (i switched to run this bot on a comp without one for now...)
        if channel == STABLE_DIFFUSION_CHANNEL_NAME_1:
            await msg.channel.send("stablediffusion disabled")
            #await gen_stable_diffusion(msg, usr_msg, chnl_num=1)
            return
        elif channel == STABLE_DIFFUSION_CHANNEL_NAME_2:
            await msg.channel.send("stablediffusion disabled")
            #await gen_stable_diffusion(msg, usr_msg, chnl_num=2)
            return

        ############################## GPT 3 REPL ##############################
        # enabled! confirmation is done through the same channel
        global GPT3_REPL_WAITING_ON_CODE_CONFIRMATION
        if channel == GPT3_REPL_CHANNEL_NAME:
            if GPT3_REPL_WAITING_ON_CODE_CONFIRMATION == False:
                GPT3_REPL_WAITING_ON_CODE_CONFIRMATION = True
                # show user the code that was generated, want confirmation to run or not
                await msg.channel.send(await gen_gpt3_repl_step_one(usr_msg))
            else:
                # we were waiting for code to be run
                GPT3_REPL_WAITING_ON_CODE_CONFIRMATION = False
                # take user input and respond appropriately
                await msg.channel.send(await gen_gpt3_repl_step_two(usr_msg))
            return

        ############################## GPT 3 ##############################
        # if sent in GPT_CHANNEL3, send back a GPT3 response
        if channel == GPT3_CHANNEL_NAME:
            # inject additional context for simple roleplay
            if GPT3_SETTINGS["chatbot_roleplay"][0] == "T":
                global CURR_CONVO_CONTEXT
                global CURR_CONVO_CONTEXT_LEN_MAX
                # remove half of oldest convo context if too long, then append the new usg_msg
                if len(CURR_CONVO_CONTEXT) > CURR_CONVO_CONTEXT_LEN_MAX:
                    CURR_CONVO_CONTEXT = CURR_CONVO_CONTEXT[len(CURR_CONVO_CONTEXT)//2 : ]
                    CURR_CONVO_CONTEXT = f"{CURR_CONVO_CONTEXT}\n\nINPUT:{usr_msg}\n\nOUTPUT:"
                # else keep adding current convo to the current context
                else:
                    CURR_CONVO_CONTEXT += f"\n\nINPUT:{usr_msg}\n\nOUTPUT:"
                
                gpt_response = await gen_gpt3(CURR_CONVO_CONTEXT)
                CURR_CONVO_CONTEXT += gpt_response

            await msg.channel.send(gpt_response)
            return

    client.run(TOKEN)