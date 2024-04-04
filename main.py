import discord
import os
from dotenv import load_dotenv
load_dotenv()
from ChatGPT import ChatGPT
from PersonalAssistant import PersonalAssistant
import argparse
from Utils import send_msg_to_usr, debug_log, runTryExcept
from Message import Message

class Main:
    def __init__(self, args : argparse.Namespace):
        # args
        debug = args.debug
        if debug: debug_log("Debug mode enabled.")

        # api keys
        self.TOKEN = os.getenv('DISCORD_TOKEN')
        assert self.TOKEN != '', "DISCORD_TOKEN environment variable not set."

        # ChatGPT
        self.ChatGPT = ChatGPT(debug)
        self.chatgpt_channel = self.ChatGPT.gpt_channel_name
        if debug: debug_log(f"Started ChatGPT with channel name: {self.chatgpt_channel}")

        # personal assistant
        self.PersonalAssistant = PersonalAssistant(debug, args.rag)
        self.personal_assistant_channel = self.PersonalAssistant.personal_assistant_channel
        if debug: debug_log(f"Started Personal Assistant with channel name: {self.personal_assistant_channel}")

        # discord
        self.intents = discord.Intents.all()
        self.client = discord.Client(intents=self.intents)
        if debug: debug_log("Started Discord Client.")

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
            
            myMsg = Message()
            myMsg.importFromDiscord(discordMsg)
            
            ############################## ChatGPT API ##############################
            if channel == self.chatgpt_channel:
                chatgptresp = await runTryExcept(self.ChatGPT.main, msg=myMsg)
                return await send_msg_to_usr(myMsg, chatgptresp)

            ############################## Personal Assistant Channel ##############################
            if channel == self.personal_assistant_channel:
                paresp = await runTryExcept(self.PersonalAssistant.main, msg=myMsg)
                return await send_msg_to_usr(myMsg, paresp)

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    # parse cli args
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="enable debug printing", action="store_true", default=False)
    parser.add_argument("-r", '--rag', help='enable RAG for Personal Assistant', action="store_true", default=False)
    args = parser.parse_args()

    # run
    bot = Main(args)
    bot.run()
