import discord
import os
from dotenv import load_dotenv
load_dotenv()
from LocalAI import StableDiffusion
from ChatGPT import ChatGPT
from PersonalAssistant import PersonalAssistant

# main class
class Main:
    '''
    General virtual assistant.
    Does a lot of things: helps you talk to a smart LLM (GPT), handle basic daily life stuff,
    creates images for you (StableDiffusion) and more!...
    '''
    def __init__(self, debug : bool):
        # api keys
        self.TOKEN = os.getenv('DISCORD_TOKEN')

        # gpt
        self.ChatGPT = ChatGPT(debug)
        self.chatgpt_channel = self.ChatGPT.gpt3_channel_name

        # stable diffusion
        self.StableDiffusion = StableDiffusion(debug)
        self.stable_diffusion_channel = self.StableDiffusion.stable_diffusion_channel

        # personal assistant
        self.PersonalAssistant = PersonalAssistant(debug)
        self.personal_assistant_channel = self.PersonalAssistant.personal_assistant_channel

        # ignore any messages not in these channels
        self.allowed_channels = [self.chatgpt_channel, self.personal_assistant_channel, self.stable_diffusion_channel]

        # discord
        self.intents = discord.Intents.all()
        self.client = discord.Client(intents=self.intents)

    def run(self):
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
                await self.PersonalAssistant.main(msg, usr_msg)
                return

            ############################## Stable Diffusion ##############################
            if channel == self.stable_diffusion_channel:
                await self.StableDiffusion.main(msg, usr_msg)
                return

            ############################## ChatGPT API ##############################
            # if sent in GPT_CHANNEL, send back a GPTX response
            if channel == self.chatgpt_channel:
                await self.ChatGPT.main(msg, usr_msg)
                return

            # if channel == os.getenv("DEV_CHANNEL"):
            #     await self.ChatGPT.testFunc(msg, usr_msg)
            #     return

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    debug = True
    if debug: print(f"DEBUG: debug printing enabled")
    bot = Main(debug)
    bot.run()