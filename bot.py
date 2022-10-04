import discord 
import responses
import os
from dotenv import load_dotenv
load_dotenv()

from discord.ext import tasks
import asyncio
import random
from datetime import datetime



async def send_message(message, user_message, is_private):
    try:
        response = responses.handle_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)
    except Exception as e:
        print(e)

def run_discord_bot():
    TOKEN = os.getenv('DISCORD_TOKEN')
    CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
    PHOTOS_DIR = os.getenv('PHOTOS_DIR')
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    quotes = []
    with open("quotes.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            quotes.append(line)
    daily_msg = "You are my love, my sunshine in this cruel, cold world. You are my light, my everything. I know you feel the same way. <3"

    @tasks.loop(seconds = 30)
    async def once_a_day_msg():
        hr_min_secs = str(datetime.now()).split()[1].split(':')
        # check time (send everyday at 7:00 am)
        if hr_min_secs[0] == '07' and hr_min_secs[1] == '00':
            ###### send msg #####
            channel = client.get_channel(CHANNEL_ID)
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

        # only respond to me when in channel "catgirl-tips", unless overrided with '!'
        if channel != "catgirl-tips":
            if usr_msg[0] == '!':
                usr_msg = usr_msg[1:]
            else:
                return

        # timely reminders!!
        if usr_msg[0:9].lower() == "remind me":
            '''expecting form: remind me, [name/msg], [time], [unit] '''
            tmp = list(map(str.strip, usr_msg.split(',')))
            task = tmp[1]
            time = int(tmp[2])
            unit = tmp[3]
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
                await send_message(msg, usr_msg, is_private=False)
                return

            await asyncio.sleep(remind_time)
            remind_msg = f"reminder: {task}"
            await send_message(msg, remind_msg, is_private=False)
            return


        # for debugging
        # print(f"{username} said {usr_msg} in {channel}")

        # if want a private message
        # if usr_msg[0] == '?':
        #     usr_msg = usr_msg[1:]
        #     await send_message(msg, usr_msg, is_private=True)
        # else:
        #     await send_message(msg, usr_msg, is_private=False)

        # general message to be catched by handle_responses()
        await send_message(msg, usr_msg, is_private=False)


    client.run(TOKEN)