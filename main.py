import discord
import os
from dotenv import load_dotenv

from ChatGPT import ChatGPT
from PersonalAssistant import PersonalAssistant
import argparse
from Utils import send_msg_to_usr, debug_log, runTryExcept
from Message import Message

class Main:
    def __init__(self, args : argparse.Namespace):
        # args
        debug = args.dev
        if debug: debug_log("Debug mode enabled.")

        # api keys
        self.TOKEN = os.getenv('DISCORD_TOKEN')
        assert self.TOKEN != '', "DISCORD_TOKEN environment variable not set."
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        assert self.openai_api_key != '', "OPENAI_API_KEY environment variable not set."

        # app data dir
        self.app_data_dir = os.getenv('APP_DATA_DIR')

        # ChatGPT
        self.chatgpt_channel = os.getenv('CHATGPT_CHANNEL')
        assert self.chatgpt_channel != '', 'ChatGPT Channel Name is not set.'
        self.ChatGPT = ChatGPT(debug=debug, api_key=self.openai_api_key, app_data_dir=self.app_data_dir)
        if debug: debug_log(f"Started ChatGPT with channel name: {self.chatgpt_channel}")

        # personal assistant
        self.personal_assistant_channel =  os.getenv('PERSONAL_ASSISTANT_CHANNEL')
        assert self.personal_assistant_channel != '', 'Personal Assistant Channel Name is not set.'
        self.PersonalAssistant = PersonalAssistant(debug=debug,
                                                   enableRAG=args.rag,
                                                   openai_api_key=self.openai_api_key,
                                                   app_data_dir=self.app_data_dir)
        if debug: debug_log(f"Started Personal Assistant with channel name: {self.personal_assistant_channel}")

        # discord
        self.intents = discord.Intents.all()
        self.client = discord.Client(intents=self.intents)
        if debug: debug_log("Started Discord Client.")

        self.DEBUG = debug

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
                if self.DEBUG:
                    chatgptresp = await self.ChatGPT.main(msg=myMsg)
                else:
                    chatgptresp = await runTryExcept(self.ChatGPT.main, msg=myMsg)

                return await send_msg_to_usr(myMsg, chatgptresp)

            ############################## Personal Assistant Channel ##############################
            if channel == self.personal_assistant_channel:
                if self.DEBUG:
                    paresp = await self.PersonalAssistant.main(msg=myMsg)
                else:
                    paresp = await runTryExcept(self.PersonalAssistant.main, msg=myMsg)
                
                return await send_msg_to_usr(myMsg, paresp)

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    # parse cli args
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", '--rag', help='enable RAG for Personal Assistant', action="store_true", default=True)
    parser.add_argument("--dev", help="enable dev mode, which also enables debug mode", action="store_true", default=False)
    args = parser.parse_args()

    # dev mode means env vars are in .env, o.w. prod env means env vars are in system
    if args.dev:
        load_dotenv()

    # run
    bot = Main(args)
    bot.run()
