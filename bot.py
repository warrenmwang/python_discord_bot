import discord
from discord.ext import tasks
import asyncio
import random
from datetime import datetime
import responses
import os
import openai
from dotenv import load_dotenv
import subprocess

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
    "chatbot_roleplay": ["F", "str"]
}

ALLOWED_CHANNELS = [MAIN_CHANNEL_NAME, GPT3_CHANNEL_NAME, STABLE_DIFFUSION_CHANNEL_NAME_1, STABLE_DIFFUSION_CHANNEL_NAME_2]

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

async def gen_gpt3(message : discord.message.Message, usr_msg : str):
    # inject additional context for simple roleplay
    if GPT3_SETTINGS["chatbot_roleplay"][0] == "T":
        usr_msg = f"{os.getenv('GPT3_ROLEPLAY_CONTEXT')} Input: {usr_msg} Output:"

    response = openai.Completion.create(
        engine = GPT3_SETTINGS["engine"][0],
        prompt = usr_msg,
                temperature = float(GPT3_SETTINGS["temperature"][0]),
                max_tokens = int(GPT3_SETTINGS["max_tokens"][0]),
                top_p = float(GPT3_SETTINGS["top_p"][0]),
                frequency_penalty = float(GPT3_SETTINGS["frequency_penalty"][0]),
                presence_penalty = float(GPT3_SETTINGS["presence_penalty"][0])
    )
    content = response.choices[0].text
    await message.channel.send(content)

async def gptsettings(msg : discord.message.Message):
    '''
    original call is:
        GPTSETTINGS

    prints out all available gpt3 settings, their current values, and their data types
    '''
    gpt3_settings = "".join([f"{key} ({GPT3_SETTINGS[key][1]}) = {GPT3_SETTINGS[key][0]}\n" for key in GPT3_SETTINGS.keys()])
    await msg.channel.send(gpt3_settings)

async def gptset(msg : discord.message.Message, usr_msg : str):
    '''
    original call is:
        GPTSET [setting_name] [new_value]

    sets the specified gpt3 parameter to the new value
    '''
    try:
        tmp = usr_msg.split()
        setting, new_val = tmp[1], tmp[2]
        GPT3_SETTINGS[setting][0] = new_val # always gonna store str
        await msg.channel.send("New parameter saved, current settings:")
        await gptsettings(msg)
    except Exception as e:
        await msg.channel.send("usage: GPTSET [setting_name] [new_value]")

############################## Main Function ##############################

def run_discord_bot():
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    @tasks.loop(seconds = 30)
    async def once_a_day_msg():
        '''
        send a glorified good morning message
        '''
        quotes = []
        with open("quotes.txt", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line == "": continue
                quotes.append(line)
        daily_msg = quotes[-1] # daily_msg is final line in quotes.txt, save then remove
        quotes = quotes[:-1]

        hr_min_secs = str(datetime.now()).split()[1].split(':')
        # check time (send everyday at 7:00 am)
        if hr_min_secs[0] == '07' and hr_min_secs[1] == '00':
        ###### send msg #####
            channel = client.get_channel(MAIN_CHANNEL_ID)
            # send msg (quote and daily personal)
            msg = f"{daily_msg}\n\n{random.choice(quotes)}"
            await channel.send(msg)
            # send an image (randomly chosen from one of my stablediffusion creations)
            img_name = random.choice(os.listdir(PHOTOS_DIR))
            img_full_path = f"{PHOTOS_DIR}/{img_name}"
            await channel.send(file=discord.File(img_full_path))
            ###### send msg #####
            await asyncio.sleep(60)

    @client.event
    async def on_ready():
        '''
        When ready, load all looping functions if any.
        '''
        print(f'{client.user} running!')
        once_a_day_msg.start()

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
            await gen_gpt3(msg, usr_msg)
            return

        # show user current GPT3 settings
        if usr_msg == "GPTSETTINGS":
            await gptsettings(msg)
            return

        # user wants to modify GPT3 settings
        if usr_msg[0:6] == "GPTSET":
            ''' expect format: GPTSET [setting_name] [new_value]'''
            await gptset(msg, usr_msg)
            return

        ############################## Custom Commands ##############################

        # Reminders based on a time
        if usr_msg[0:9].lower() == "remind me":
            '''expecting form: remind me, [name/msg], [time], [unit] '''
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

        # Python Calculator
        # slightly danger zone where I'm running code...
        if usr_msg[0:5] == 'calc:':
            try:
                tmp = usr_msg.split(":")
                await msg.channel.send(eval(tmp[1]))
            except Exception as e:
                await msg.channel.send("usage: calc: [math exp in python]")    
            return

        # Dice Roller
        if usr_msg == "diceroll":
            await msg.channel.send(str(random.randint(1, 6)))
            return

        ############################## For Hard Coded Response ##############################
        # general message to be catched by handle_responses() -- hard coded responses
        try:
            response = responses.handle_response(usr_msg)
            await msg.channel.send(response)
        except Exception as e:
            print(e)

    client.run(TOKEN)
