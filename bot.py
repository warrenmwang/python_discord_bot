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
########## END GLOBAL VARS ##########


async def gen_gpt3(message, usr_msg):
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt= usr_msg,
                temperature = 0.7,
                max_tokens= 100,
                top_p = 1,
                frequency_penalty=0,
                presence_penalty=0
    )
    content = response.choices[0].text
    await message.channel.send(content)

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
        quotes = []
        with open("quotes.txt", "r") as f:
            lines = f.readlines()
            for line in lines:
                quotes.append(line)
        daily_msg = "You are my love, my sunshine in this cruel, cold world. You are my light, my everything. I know you feel the same way. <3"

        global MAIN_CHANNEL_ID
        global PHOTOS_DIR
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
            print(f"sent msg at {datetime.now()}")
            await asyncio.sleep(60)

    @client.event
    async def on_ready():
        print(f'{client.user} running!')
        once_a_day_msg.start()

    @client.event
    async def on_message(msg):
        if msg.author == client.user:
            return 
        
        username = str(msg.author)
        usr_msg = str(msg.content)
        channel = str(msg.channel)

        # for debugging
        # print(f"{username}\n{usr_msg}\n{channel}")

        # if sent in GPT_CHANNEL3, send back a GPT3 response
        if channel == GPT3_CHANNEL_NAME:
            await gen_gpt3(msg, usr_msg)
            return

        # only respond to me when in channel MAIN_CHANNEL, unless overrided with '!'
        if channel != MAIN_CHANNEL_NAME:
            if usr_msg[0] == '!':
                usr_msg = usr_msg[1:]
            else:
                return

        # Reminders based on a time
        if usr_msg[0:9].lower() == "remind me":
            '''expecting form: remind me, [name/msg], [time], [unit] '''
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
                usr_msg  = "reminder: Unknown time unit. Aborting."
                await send_message(msg, usr_msg)
                return

            await asyncio.sleep(remind_time)
            remind_msg = f"reminder: {task}"
            await send_message(msg, remind_msg)
        # general message to be catched by handle_responses()
        else:
            await send_message(msg, usr_msg)


    client.run(TOKEN)