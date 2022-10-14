import discord
from discord.ext import tasks
import asyncio
import random
from datetime import datetime
import os
import openai
from dotenv import load_dotenv
import subprocess

# give calculator more advanced math capabilities
import numpy as np

# web scraping stuff
import requests, bs4

load_dotenv()

############################## GLOBAL VARS ##############################
TOKEN = os.getenv('DISCORD_TOKEN')
MAIN_CHANNEL_ID = int(os.getenv('MAIN_CHANNEL_ID'))
PHOTOS_DIR = os.getenv('PHOTOS_DIR')
MAIN_CHANNEL_NAME = os.getenv('MAIN_CHANNEL_NAME')

STABLE_DIFFUSION_CHANNEL_NAME_1 = os.getenv('STABLE_DIFFUSION_CHANNEL_NAME_1')
STABLE_DIFFUSION_CHANNEL_NAME_2 = os.getenv('STABLE_DIFFUSION_CHANNEL_NAME_2')
STABLE_DIFFUSION_PYTHON_BIN_PATH = os.getenv('STABLE_DIFFUSION_PYTHON_BIN_PATH')
STABLE_DIFFUSION_SCRIPT_PATH = os.getenv('STABLE_DIFFUSION_SCRIPT_PATH')
STABLE_DIFFUSION_ARGS_1 = os.getenv('STABLE_DIFFUSION_ARGS_1')
STABLE_DIFFUSION_ARGS_2 = os.getenv('STABLE_DIFFUSION_ARGS_2')
STABLE_DIFFUSION_OUTPUT_DIR = os.getenv('STABLE_DIFFUSION_OUTPUT_DIR')

openai.api_key = os.getenv('GPT3_OPENAI_API_KEY')
GPT3_CHANNEL_NAME = os.getenv('GPT3_CHANNEL_NAME')
GPT3_SETTINGS = {
    "engine": ["text-davinci-002", "str"],
    "temperature": ["0.7", "float"],
    "max_tokens": ["100", "int"],
    "top_p": ["1.0", "float"],
    "frequency_penalty": ["0", "float"],
    "presence_penalty": ["0", "float"],
    "chatbot_roleplay": ["T", "str"]
}
MY_NAME = os.getenv('MY_NAME')
MY_DREAM = os.getenv('MY_DREAM')
MY_CURRENT_LOCATION = os.getenv('MY_CURRENT_LOCATION')

PERSONAL_ASSISTANT_CHANNEL = os.getenv('PERSONAL_ASSISTANT_CHANNEL')

ALLOWED_CHANNELS = [MAIN_CHANNEL_NAME, GPT3_CHANNEL_NAME, STABLE_DIFFUSION_CHANNEL_NAME_1, STABLE_DIFFUSION_CHANNEL_NAME_2, PERSONAL_ASSISTANT_CHANNEL]

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

    # send image(s) back to user
    imgs_to_send = []
    for file in os.listdir(STABLE_DIFFUSION_OUTPUT_DIR):
        file_path = os.path.join(STABLE_DIFFUSION_OUTPUT_DIR, file)
        if file_path[-4:] == ".png":
            imgs_to_send.append(file_path)
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

async def gen_gpt3(usr_msg : str, settings_dict: dict = GPT3_SETTINGS) -> str:
    '''
    retrieves a GPT3 response given a string input and a dictionary containing the settings to use
    returns the response str
    '''
    response = openai.Completion.create(
        engine = settings_dict["engine"][0],
        prompt = usr_msg,
                temperature = float(settings_dict["temperature"][0]),
                max_tokens = int(settings_dict["max_tokens"][0]),
                top_p = float(settings_dict["top_p"][0]),
                frequency_penalty = float(settings_dict["frequency_penalty"][0]),
                presence_penalty = float(settings_dict["presence_penalty"][0])
    )
    return response.choices[0].text

async def gptsettings(msg : discord.message.Message) -> None:
    '''
    original call is:
        GPTSETTINGS

    prints out all available gpt3 settings, their current values, and their data types
    '''
    await msg.channel.send("".join([f"{key} ({GPT3_SETTINGS[key][1]}) = {GPT3_SETTINGS[key][0]}\n" for key in GPT3_SETTINGS.keys()]))

async def gptset(usr_msg : str) -> None:
    '''
    original call is:
        GPTSET [setting_name] [new_value]

    sets the specified gpt3 parameter to the new value
    '''
    tmp = usr_msg.split()
    setting, new_val = tmp[1], tmp[2]
    GPT3_SETTINGS[setting][0] = new_val # always gonna store str


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
    # Reminders based on a time
    if usr_msg[0:9].lower() == "remind me":
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
    if usr_msg.lower() == "weather":
        await msg.channel.send(await get_weather_data(MY_CURRENT_LOCATION))
        return

    # Calculator
    if usr_msg[0:5].lower() == 'calc:':
        try:
            tmp = usr_msg.split(":")
            await msg.channel.send(eval(tmp[1]))
        except Exception as e:
            await msg.channel.send("usage: calc: [math exp in python (available libraries include: numpy)]")
        return

    # Time
    if usr_msg[0:5].lower() == 'time':
        tmp = str(datetime.now()).split()
        date, time_24_hr = tmp[0], tmp[1]
        await msg.channel.send(f"Date: {date}\nTime 24H: {time_24_hr}")
        return

    await msg.channel.send("That was command found.")

############################## Main Function ##############################

def run_discord_bot():
    '''
    Main loop
    '''
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    @tasks.loop(seconds = 30)
    async def msgs_on_loop():
        hr_min_secs = str(datetime.now()).split()[1].split(':')
        msgs_on_loop_channel = client.get_channel(MAIN_CHANNEL_ID)
        msgs_on_loop_gpt_settings = {
                "engine": ["text-davinci-002", "str"],
                "temperature": ["0.7", "float"],
                "max_tokens": ["200", "int"],
                "top_p": ["1.0", "float"],
                "frequency_penalty": ["0", "float"],
                "presence_penalty": ["0", "float"],
            }

        # send a good morning msg at 7:00am
        quotes = []
        with open("quotes.txt", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line == "": continue
                quotes.append(line)
        daily_msg = quotes[-1] # daily_msg is final line in quotes.txt, save then remove
        quotes = quotes[:-1]
        if hr_min_secs[0] == '07' and hr_min_secs[1] == '00':
            msg = f"{daily_msg}\n\n{random.choice(quotes)}"
            await msgs_on_loop_channel.send(msg)
            img_name = random.choice(os.listdir(PHOTOS_DIR))
            img_full_path = f"{PHOTOS_DIR}/{img_name}"
            await msgs_on_loop_channel.send(file=discord.File(img_full_path))
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

    @client.event
    async def on_ready():
        '''
        When ready, load all looping functions if any.
        '''
        print(f'{client.user} running!')
        msgs_on_loop.start()

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

        ############################## StableDiffusion ##############################

        if channel == STABLE_DIFFUSION_CHANNEL_NAME_1:
            await gen_stable_diffusion(msg, usr_msg, chnl_num=1)
            return
        elif channel == STABLE_DIFFUSION_CHANNEL_NAME_2:
            await gen_stable_diffusion(msg, usr_msg, chnl_num=2)
            return

        ############################## GPT 3 ##############################
        # if sent in GPT_CHANNEL3, send back a GPT3 response
        if channel == GPT3_CHANNEL_NAME:
            # inject additional context for simple roleplay
            if GPT3_SETTINGS["chatbot_roleplay"][0] == "T":
                usr_msg = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} {MY_NAME}: {usr_msg} You:"
            await msg.channel.send(await gen_gpt3(usr_msg))
            return

        # show user current GPT3 settings
        if usr_msg == "GPTSETTINGS":
            await gptsettings(msg)
            return

        # user wants to modify GPT3 settings
        if usr_msg[0:6] == "GPTSET":
            ''' expect format: GPTSET [setting_name] [new_value]'''
            try:
                await gptset(usr_msg)
                await msg.channel.send("New parameter saved, current settings:")
                await gptsettings(msg)
            except Exception as e:
                await msg.channel.send("usage: GPTSET [setting_name] [new_value]")
            return

        ############################## Personal Assistant Channel ##############################
        if channel == PERSONAL_ASSISTANT_CHANNEL:
            await personal_assistant_block(msg, usr_msg)
            return

        ############################## Final Catch ##############################
        if channel == MAIN_CHANNEL_NAME:
            await msg.channel.send("I'm sorry, this channel is only for me now >:)")


    client.run(TOKEN)
