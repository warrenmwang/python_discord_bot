import discord
import os
from dotenv import load_dotenv
load_dotenv()
from LocalAI import StableDiffusion
from ChatGPT import ChatGPT
from PersonalAssistant import PersonalAssistant
import argparse
from Utils import send_msg_to_usr, debug_log, runTryExcept
import uuid
from Message import Message

class Main:
    def __init__(self, args : argparse.Namespace):
        # args
        debug = args.debug
        self.stable_diffusion_enabled = args.stable_diffusion
        if debug: debug_log("Debug mode enabled.")
        if debug: debug_log(f"Stable Diffusion enabled: {self.stable_diffusion_enabled}")

        # api keys
        self.TOKEN = os.getenv('DISCORD_TOKEN')
        assert self.TOKEN != '', "DISCORD_TOKEN environment variable not set."

        # ChatGPT
        self.ChatGPT = ChatGPT(debug)
        self.chatgpt_channel = self.ChatGPT.gpt_channel_name
        if debug: debug_log(f"Started ChatGPT with channel name: {self.chatgpt_channel}")

        # stable diffusion
        if self.stable_diffusion_enabled:
            self.StableDiffusion = StableDiffusion(debug)
            self.stable_diffusion_channel = self.StableDiffusion.stable_diffusion_channel
            if debug: debug_log(f"Started Stable Diffusion with channel name: {self.stable_diffusion_channel}")
        else:
            self.stable_diffusion_channel = uuid.uuid4().hex
            if debug: debug_log(f"Stable Diffusion is not enabled. Continuing.")

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
                # return await send_msg_to_usr(msg, await self.PersonalAssistant.main(msg))
                paresp = await runTryExcept(self.PersonalAssistant.main, msg=myMsg)
                # paresp = await self.PersonalAssistant.main(msg=myMsg)
                return await send_msg_to_usr(myMsg, paresp)

            ############################## Stable Diffusion ##############################
            if channel == self.stable_diffusion_channel:
                if self.stable_diffusion_enabled:
                    return await self.StableDiffusion.main(myMsg)
                else:
                    return await send_msg_to_usr(myMsg, "Stable Diffusion is not enabled.")            

        self.client.run(self.TOKEN)

if __name__ == "__main__":
    # parse cli args
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="enable debug printing", action="store_true", default=False)
    parser.add_argument("-s", '--stable_diffusion', help="enable stable diffusion", action="store_true", default=False)
    parser.add_argument("-r", '--rag', help='enable RAG for Personal Assistant', action="store_true", default=False)
    args = parser.parse_args()

    # run
    bot = Main(args)
    bot.run()
