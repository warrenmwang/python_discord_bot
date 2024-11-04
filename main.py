import discord
import os
from dotenv import load_dotenv

from ChatGPT import ChatGPT
from PersonalAssistant import PersonalAssistant
import argparse
from Utils import send_msg_to_usr, debug_log, runTryExcept, Message

class Main:
    def __init__(self, args : argparse.Namespace):
        # args
        debug = args.dev
        if debug: debug_log('Debug mode enabled.')

        # environment variables
        discord_token = os.getenv('DISCORD_TOKEN')
        openai_api_key = os.getenv("OPENAI_API_KEY")
        app_data_dir = os.getenv('APP_DATA_DIR')
        chatgpt_channel = os.getenv('CHATGPT_CHANNEL')
        personal_assistant_channel =  os.getenv('PERSONAL_ASSISTANT_CHANNEL')

        assert discord_token is not None and discord_token != '', 'DISCORD_TOKEN environment variable not found.'
        assert openai_api_key is not None and openai_api_key != '', 'OPENAI_API_KEY environment variable not found.'
        assert app_data_dir is not None and app_data_dir != '', 'APP_DATA_DIR environment variable not found.'
        assert chatgpt_channel is not None and chatgpt_channel != '', 'CHATGPT_CHANNEL environment variable not found.'
        assert personal_assistant_channel is not None and personal_assistant_channel != '',\
        'Personal Assistant Channel Name is not set.'

        self.TOKEN = discord_token
        self.openai_api_key = openai_api_key
        self.app_data_dir = app_data_dir
        self.chatgpt_channel = chatgpt_channel
        self.personal_assistant_channel =  personal_assistant_channel

        # ChatGPT
        self.ChatGPT = ChatGPT(debug=debug, api_key=self.openai_api_key, app_data_dir=self.app_data_dir)
        if debug: debug_log(f'Started ChatGPT with channel name: {self.chatgpt_channel}')

        # personal assistant
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
        print("[LOG] Running in dev mode.")
    else:
        print("[LOG] Running in prod mode.")

    # run
    bot = Main(args)
    bot.run()
