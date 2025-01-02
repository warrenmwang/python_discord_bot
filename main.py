import discord
import os
from dotenv import load_dotenv

from GenerativeAI import LLM_Controller
from PersonalAssistant import PersonalAssistant
import argparse
from Utils import runTryExcept, Message

class Main:
    def __init__(self, debug: bool):
        self.DEBUG = debug

        discord_token = os.getenv('DISCORD_TOKEN', "")
        chatgpt_channel = os.getenv('CHATGPT_CHANNEL', "")
        personal_assistant_channel =  os.getenv('PERSONAL_ASSISTANT_CHANNEL', "")

        assert discord_token != '', 'DISCORD_TOKEN environment variable not found.'
        assert chatgpt_channel != '', 'CHATGPT_CHANNEL environment variable not found.'
        assert personal_assistant_channel != '', 'Personal Assistant Channel Name is not set.'

        self.TOKEN = discord_token
        self.chatgpt_channel = chatgpt_channel
        self.personal_assistant_channel =  personal_assistant_channel

        self.LLM_API = LLM_Controller()
        self.PersonalAssistant = PersonalAssistant()

        # discord
        self.intents = discord.Intents.all()
        self.client = discord.Client(intents=self.intents)

    def run(self):
        '''Main function'''
        ########################### INIT ############################
        @self.client.event
        async def on_ready():
            '''When ready, load all looping functions if any.'''
            print(f'{self.client.user} running!')

        ########################### ON ANY MSG ############################

        @self.client.event
        async def on_message(discordMsg : discord.message.Message):
            '''Entrance function for any message sent to any channel in the guild/server.'''
            channel = str(discordMsg.channel)

            ############################## Checks for not doing anything ##############################
            # bot doesn't response to self
            if discordMsg.author == self.client.user:
                return 

            msg = Message.from_discord(discordMsg)

            ############################## LLM API (OpenAI models, Anthropic Models, etc.) ##############################
            if channel == self.chatgpt_channel:
                if self.DEBUG:
                    chatgptresp = await self.LLM_API.main(msg=msg)
                else:
                    chatgptresp = await runTryExcept(self.LLM_API.main, msg=msg)

                return await Message.send_msg_to_usr(msg, chatgptresp)

            ############################## Personal Assistant Channel ##############################
            if channel == self.personal_assistant_channel:
                if self.DEBUG:
                    paresp = await self.PersonalAssistant.main(msg=msg)
                else:
                    paresp = await runTryExcept(self.PersonalAssistant.main, msg=msg)

                return await Message.send_msg_to_usr(msg, paresp)

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    # parse cli args
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", help="enable dev mode, which also enables debug mode", action="store_true", default=False)
    args = parser.parse_args()

    # dev mode means env vars are in .env, o.w. prod env means env vars are in system
    if args.dev:
        load_dotenv()
        print("[LOG] Running in dev mode.")
    else:
        print("[LOG] Running in prod mode.")

    Main(args.dev).run()
