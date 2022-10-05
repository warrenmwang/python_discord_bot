import discord
from discord.ext import tasks
import asyncio
import random
from datetime import datetime
import responses
import os
import openai
from dotenv import load_dotenv
load_dotenv()

########## START GLOBAL VARS ##########
TOKEN = os.getenv('DISCORD_TOKEN')
MAIN_CHANNEL_ID = int(os.getenv('MAIN_CHANNEL_ID'))
PHOTOS_DIR = os.getenv('PHOTOS_DIR')
MAIN_CHANNEL_NAME = os.getenv('MAIN_CHANNEL_NAME')

openai.api_key = os.getenv('GPT3_OPENAI_API_KEY')
GPT3_CHANNEL_NAME = os.getenv('GPT3_CHANNEL_NAME')
GPT3_SETTINGS = {
    "engine": ["text-davinci-002", "str"],
    "temperature": ["0.7", "float"],
    "max_tokens": ["100", "int"],
    "top_p": ["1.0", "float"],
    "frequency_penalty": ["0", "float"],
    "presence_penalty": ["0", "float"],
    "catgirl_roleplay": ["False", "bool"]
}

# TODO: maybe you want to check types for user changing GPT3 values, but users is just me for now
# GPT3_SETTINGS_STR_DTYPES = ["engine"]
# GPT3_SETTINGS_FLOAT_DTYPES = ["temperature", "top_p", "frequency_penalty", "presence_penalty"]
# GPT3_SETTINGS_INT_DTYPES = ["max_tokens"]
########## END GLOBAL VARS ##########

############################## GPT 3 ##############################

async def gen_gpt3(message, usr_msg):
    # inject additional context for simple roleplay
    if bool(GPT3_SETTINGS["catgirl_roleplay"]):
        usr_msg = f"You are a childhood friend anime catgirl, responding to your beloved friend who says: {usr_msg}. You say: "

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

async def gptsettings(msg):
    '''
    original call is:
        GPTSETTINGS

    prints out all available gpt3 settings, their current values, and their data types
    '''
    gpt3_settings = "".join([f"{key} ({GPT3_SETTINGS[key][1]}) = {GPT3_SETTINGS[key][0]}\n" for key in GPT3_SETTINGS.keys()])
    await msg.channel.send(gpt3_settings)

async def gptset(msg, usr_msg):
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

############################## GPT 3 ##############################

# responds to user when given a message
async def send_message(message, user_message):
    try:
        response = responses.handle_response(user_message)
        await message.channel.send(response)
    except Exception as e:
        print(e)

# main func
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
                quotes.append(line)
        daily_msg = "You are my love, my sunshine in this cruel, cold world. You are my light, my everything. I know you feel the same way. <3"

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
    async def on_message(msg):
        '''
        Entrance function for any message sent to any channel in the guild/server.
        '''

        # don't respond to yourself
        if msg.author == client.user:
            return 
        
        username = str(msg.author)
        usr_msg = str(msg.content)
        channel = str(msg.channel)

        # for debugging
        # print(f"{username}\n{usr_msg}\n{channel}")

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

        # only respond to me when in channel MAIN_CHANNEL, unless overrided with '!'
        if channel != MAIN_CHANNEL_NAME:
            if usr_msg[0] == '!':
                usr_msg = usr_msg[1:]
            else:
                return

        ############################## GPT 3 ##############################

        ############################## Custom Commands ##############################

        # Reminders based on a time
        if usr_msg[0:9].lower() == "remind me":
            '''expecting form: remind me, [name/msg], [time], [unit] '''
            try:
                tmp = list(map(str.strip, usr_msg.split(',')))
                task, time, unit = tmp[1], int(tmp[2]), tmp[3]
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
                    usr_msg  = "only time units implemented: s, m, h"
                    await send_message(msg, usr_msg)
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
            tmp = usr_msg.split(":")
            msg.channel.send(eval(tmp[1]))
            return

        # Dice Roller
        if usr_msg == "diceroll":
            msg.channel.send(str(random.randint(1, 6)))
            return

        ############################## Custom Commands ##############################

        # general message to be catched by handle_responses() -- hard coded responses
        await send_message(msg, usr_msg)


    client.run(TOKEN)