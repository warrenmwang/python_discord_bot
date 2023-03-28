import discord
from discord.ext import tasks
from discord import FFmpegPCMAudio
import asyncio
import shlex
from datetime import datetime
import os
import openai
from dotenv import load_dotenv
import subprocess

from gpt3_repl import answer_one_question_step_one, answer_one_question_step_two, GPT3_REPL_SETTINGS

load_dotenv()


class BMO:
    def __init__(self):
        ############################## vals needed ##############################
        self.TOKEN = os.getenv('DISCORD_TOKEN')

        self.stable_diffusion_channel = os.getenv('STABLE_DIFFUSION_CHANNEL')
        self.stable_diffusion_script = os.getenv('STABLE_DIFFUSION_SCRIPT')
        self.waifu_diffusion_channel = os.getenv('WAIFU_DIFFUSION_CHANNEL')
        self.waifu_diffusion_script = os.getenv('WAIFU_DIFFUSION_SCRIPT')
        self.stable_diffusion_output_dir = os.getenv('STABLE_DIFFUSION_OUTPUT_DIR')

        # self.my_name = os.getenv('MY_NAME')
        # self.my_dream = os.getenv('MY_DREAM')

        # different api keys
        self.GPT3_OPENAI_API_KEY = os.getenv("GPT3_OPENAI_API_KEY")
        self.CODEX_OPENAI_API_KEY = os.getenv("CODEX_OPENAI_API_KEY")

        self.gpt3_channel_name = os.getenv('GPT3_CHANNEL_NAME')
        self.gpt3_channel_id = os.getenv('GPT3_CHANNEL_ID')
        self.gpt3_settings = {
            "model": ["gpt-3.5-turbo", "str"],
            "messages" : [[], "list of dicts"],
            "temperature": ["0.0", "float"],
            "top_p": ["1.0", "float"],
            "frequency_penalty": ["0", "float"],
            "presence_penalty": ["0", "float"],
            "chatbot_roleplay": ["T", "str"],
        }
        self.discord_msglen_cap = 2000
        self.chatgpt_name="assistant"

        self.daily_reminders_switch = False # initially off
        self.personal_assistant_channel = os.getenv('PERSONAL_ASSISTANT_CHANNEL')
        self.gpt3_repl_channel_name = os.getenv("GPT3_REPL_CHANNEL_NAME")
        self.gpt3_repl_working_prompt_filename = os.getenv("GPT3_REPL_WORKING_PROMPT_FILENAME")
        self.gpt3_repl_waiting_on_code_confirmation = False
        self.gpt3_repl_script_filename = os.getenv("GPT3_REPL_SCRIPT_FILENAME")

        # we can have multiple GPT3 convo contexts, init with the roleplay one
        # self.gpt3_prompt_personal_assistant_file=os.getenv("GPT3_PROMPT_PERSONAL_ASSISTANT_FILE")
        # self.gpt3_prompt_roleplay_file=os.getenv("GPT3_PROMPT_ROLEPLAY_FILE")

        # gpt prompts
        self.gpt_prompts_file = os.getenv("GPT_PROMPTS_FILE")
        self.all_gpt3_available_prompts = [] # list of all prompt names
        self.map_promptname_to_prompt = {} # (k,v) = (prompt_name, prompt_as_str)
        self.curr_prompt_name = None  # name of prompt we're currently using
        self.curr_convo_context = None # string of all curr convo

        self.allowed_channels = [self.gpt3_channel_name, self.stable_diffusion_channel, self.waifu_diffusion_channel, self.personal_assistant_channel, self.gpt3_repl_channel_name]

        self.intents = discord.Intents.all()
        self.client = discord.Client(intents=self.intents)

    ############################## STABLE DIFFUSION ##############################

    async def gen_stable_diffusion(self, msg : discord.message.Message, usr_msg : str, chnl_num : int) -> None:
        '''
        takes in usr_msg as the prompt (and generation params, don't need to include outdir, automatically added)
        and generate image(s) using stablediffusion, then send them back to the user
        '''
        # first generate image(s)
        if chnl_num == 1:
            # stable diffusion
            cmd = f"{self.stable_diffusion_script} \"{usr_msg}\""
        else:
            # waifu diffusion
            cmd = f"{self.waifu_diffusion_script} \"{usr_msg}\""

        try:
            subprocess.run(cmd, shell=True)
        except Exception as e:
            await msg.channel.send(f"StableDiffusion: got error on subprocess: {e}")
            return

        # get generated image(s), if any
        imgs_to_send = []
        for file in os.listdir(self.stable_diffusion_output_dir):
            file_path = os.path.join(self.stable_diffusion_output_dir, file)
            if file_path[-4:] == ".png":
                imgs_to_send.append(file_path)
        # if no images were generated, send notify usr
        if len(imgs_to_send) == 0:
            await msg.channel.send(f"StableDiffusion: no images generated (probably CUDA out of memory)")
        else:
            # have images, send them
            for img in imgs_to_send:
                await msg.channel.send(file=discord.File(img))

        # delete all png files in outputdir
        for file in os.listdir(self.stable_diffusion_output_dir):
            file_path = os.path.join(self.stable_diffusion_output_dir, file)
            try:
                if file_path[-4:] == ".png":
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
            except Exception as e:
                await msg.channel.send("something went wrong in cleanup procedure in stable diffusion")

    ############################## GPT REPL ##############################

    async def gen_gpt3_repl_step_one(self, usr_msg : str) -> str:
        '''
        1. try to answer the question immediately
        2. if cannot, then generate python code and send that to user
        3. then need to await confirmation to run the code or not (go to step 2 function)


        receives a str prompt that should be passed into a gpt3 generation under the context
        that GPT3 is serving as a repl that generates code if needed and provides an answer
        '''
        openai.api_key = self.CODEX_OPENAI_API_KEY
        if (answer_one_question_step_one(usr_msg) == 1):
            # direct answer is available
            with open(self.gpt3_repl_working_prompt_filename, "r") as f:
                tmp = f.readlines()
                answer = tmp[-1] # get answer (expect one line answers for now)
            os.unlink(self.gpt3_repl_working_prompt_filename) # cleanup by deleting the working prompt file
            return answer
        else:
            # show to user the python script generated, ask for confirmation before running code
            ret_str = f"This is the full script:\n==========\n"
            with open(self.gpt3_repl_script_filename, "r") as f:
                ret_str += f.read()
            ret_str += "==========\nDoes this look ok to run? [y/n]"
            return ret_str

    async def gen_gpt3_repl_step_two(self, usr_msg: str) -> str:
        '''
        usr_msg should be either [y/n]

        if y run python script and return the answer
        if n abort and cleanup

        give all this work to the func
        '''
        ret_str = answer_one_question_step_two(usr_msg)
        return ret_str

    ############################## GPT3 ##############################
    async def gpt_prompt_initializer(self) -> None:
        '''
        loads in all the prompts from the prompt files
        '''
        # load in all the prompts
        with open(self.gpt_prompts_file, "r") as f:
            lines = f.readlines()
            
            # format is each line has [prompt_name] [prompt], the separator is <SEP>
            for line in lines:
                line = line.strip()
                prompt_name = line.split("<SEP>")[0]
                prompt = line.split("<SEP>")[1]
                self.all_gpt3_available_prompts.append(prompt_name)
                self.map_promptname_to_prompt[prompt_name] = prompt

        # init with first prompt
        self.curr_prompt_name = self.all_gpt3_available_prompts[0]
        await self.gpt_context_reset()

    async def gpt_context_reset(self) -> None:
        '''
        resets the gpt3 context
        > can be used at the start of program run and whenever a reset is wanted
        '''
        self.curr_convo_context = self.map_promptname_to_prompt[self.curr_prompt_name]
        self.gpt3_settings["messages"][0] = [] # reset messages, should be gc'd
        self.gpt3_settings["messages"][0].append({"role":self.chatgpt_name, "content":self.curr_convo_context})

    async def gen_gpt3(self, usr_msg : str, settings_dict: dict = None) -> str:
        '''
        retrieves a GPT3 response given a string input and a dictionary containing the settings to use
        returns the response str
        '''
        openai.api_key = self.GPT3_OPENAI_API_KEY

        if settings_dict is None:
            settings_dict = self.gpt3_settings

        # update log(list) of messages, then use it to query
        settings_dict["messages"][0].append({"role": "user", "content": usr_msg})
        # query
        response = openai.ChatCompletion.create(
            model = settings_dict["model"][0],
            messages = settings_dict["messages"][0],
            temperature = float(settings_dict["temperature"][0]),
            # max_tokens = int(settings_dict["max_tokens"][0]),
            top_p = float(settings_dict["top_p"][0]),
            frequency_penalty = float(settings_dict["frequency_penalty"][0]),
            presence_penalty = float(settings_dict["presence_penalty"][0]),
            # stop = settings_dict["stop"][0]
        )
        return response['choices'][0]['message']['content']

    async def gptsettings(self, msg : discord.message.Message, gpt3_settings : dict) -> None:
        '''
        prints out all available gpt3 settings, their current values, and their data types
        '''
        await self.send_msg_to_usr(msg, "".join([f"{key} ({gpt3_settings[key][1]}) = {gpt3_settings[key][0]}\n" for key in gpt3_settings.keys()]))

    async def gptset(self, usr_msg : str, gpt3_settings : dict) -> None:
        '''
        original call is:
            GPTSET [setting_name] [new_value]

        sets the specified gpt3 parameter to the new value
        '''
        tmp = usr_msg.split()
        setting, new_val = tmp[1], tmp[2]
        gpt3_settings[setting][0] = new_val # always gonna store str
        
    async def send_msg_to_usr(self, msg : discord.message.Message, usr_msg : str): 
        '''
        in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
        the damn message (whether it be one or multiple messages)
        '''
        diff = len(usr_msg)
        start = 0
        end = self.discord_msglen_cap
        while diff > 0:
            await msg.channel.send(usr_msg[start:end])
            start = end
            end += self.discord_msglen_cap
            diff -= self.discord_msglen_cap

    ###### Voice Channel ######

    async def join_vc(self, msg : discord.message.Message) -> None:
        '''
        joins the voice channel that the user is currently in
        '''
        if msg.author.voice:
            channel = msg.author.voice.channel
            voice = await channel.connect()
            source = FFmpegPCMAudio('nevergonnagiveyouup.m4a')
            player = voice.play(source)
        else:
            await msg.channel.send("You are not in a voice channel")

    async def leave_vc(self, msg : discord.message.Message) -> None:
        '''
        leaves the voice channel that the bot is currently in
        '''
        if msg.guild.voice_client:
            await msg.guild.voice_client.disconnect()
        else:
            await msg.channel.send("I am not in a voice channel")

    #### Alpaca ####
    async def alpaca(self, msg : discord.message.Message, usr_msg : str) -> None:
        ''''
        generate response using alpaca.cpp 7B model (this laptop is old)
        and send the reply
        '''
        # run the bash script alpaca.sh with the usr_msg as the argument, and get the response in alpaca_response.txt
        cmd = f"./alpaca.sh {shlex.quote(usr_msg)}"
        try:
            # subprocess.run(cmd, shell=True)
            proc = await asyncio.create_subprocess_shell(cmd)
            await proc.wait() # Wait for the process to complete
        except Exception as e:
            await msg.channel.send(f"alpaca got error: {e}")
            return

        # read the response from the file
        with open("./alpaca.cpp/alpaca_response.txt", "r") as f:
            response = f.read()

        # send the response
        await self.send_msg_to_usr(msg, f"alpaca: {response}")

        # cleanup
        os.system("rm ./alpaca.cpp/alpaca_response.txt")

    ############################## Personal Assistant ##############################
    async def personal_assistant_block(self, msg : discord.message.Message, usr_msg: str) -> None:
        '''
        Custom commands that do a particular hard-coded thing.
        '''
        usr_msg = usr_msg.lower()

        # list all the commands available
        if usr_msg == "help":
            help_str = \
            "List of available commands:\n\
            help: show this message\n\
            remind me: reminders\n\
            daily reminders: show current status of daily reminders\n\
            daily reminders toggle: toggle the daily reminders\n\nGPT Settings:\n\n\
            convo len: show current gpt3 context length\n\
            reset thread: reset gpt3 context length\n\
            show thread: show the entire current convo context\n\
            gptsettings: show the current gpt3 settings\n\
            gptreplsettings: show gpt3 repl settings\n\
            gptset [setting_name] [new_value]: modify gpt3 settings\n\
            gptreplset [setting_name] [new_value]: modify gpt3 repl settings\n\
            curr prompt: get the current prompt name\n\
            change prompt, [new prompt]: change prompt to the specified prompt\n\
            show prompts: show the available prompts for gpt3\n\
            \n\n\
            Voice Channel:\n\
            join_vc: join the voice channel of the user\n\
            leave_vc: bot leaves the voice channel it's in\n\
            Alpaca:\n\
            alpaca [prompt]: get a response from alpaca\n\
            "
            await msg.channel.send(help_str)
            return

        # alpaca
        if usr_msg[:6] == "alpaca":
            prompt = usr_msg[7:]

            # don't generate for empty messages
            if len(prompt) == 0:
                await self.send_msg_to_usr(msg, "alpaca got empty message, abort generating response")
                return

            await self.send_msg_to_usr(msg, f"Generating a response to the prompt: {prompt}")
            await self.alpaca(msg, prompt)
            return

        # join the voice channel of the user
        if usr_msg == "join_vc":
            await self.join_vc(msg)
            return

        # leave the voice channel of the bot
        if usr_msg == "leave_vc":
            await self.leave_vc(msg)
            return
        
        # show the current gpt3 prompt
        if usr_msg == "curr prompt":
            await msg.channel.send(self.curr_prompt_name)
            return

        # TODO: add a command to add a new prompt to the list of prompts and save to file

        # TODO: add a command to update a prompt (no renames allowed)

        # TODO: add a command to delete a prompt (just remove from the list of prompts and save to file), probably need to rerun the gpt_prompt_initializer func after

        # change gpt3 prompt
        if usr_msg[:13] == "change prompt":
            # accept only the prompt name, update both str of msgs context and the messages list in gptsettings
            try:
                self.curr_prompt_name = list(map(str.strip, usr_msg.split(',')))[1]
                self.curr_convo_context = self.map_promptname_to_prompt[self.curr_prompt_name]
                await self.gpt_context_reset()
                await msg.channel.send("New current prompt set to: " + self.curr_prompt_name)
                return
            except Exception as e:
                await msg.channel.send("usage: change prompt, [new prompt]")
                return

        # show available prompts as (ind. prompt)
        if usr_msg == "show prompts":
            x = "".join([f"Name: {k}\nPrompt:{v}\n----\n" for k,v in self.map_promptname_to_prompt.items()])
            await msg.channel.send(x) 
            return 

        if usr_msg == "daily reminders":
            x = "ON" if self.daily_reminders_switch else "OFF"
            await msg.channel.send(x)
            return

        if usr_msg == "daily reminders toggle":
            self.daily_reminders_switch = False if self.daily_reminders_switch else True
            await msg.channel.send(f"Set to: {'ON' if self.daily_reminders_switch else 'OFF'}")
            return

        # gpt3 repl settings
        if usr_msg == "gptreplsettings":
            await self.gptsettings(msg, GPT3_REPL_SETTINGS)
            return

        # show user current GPT3 settings
        if usr_msg == "gptsettings":
            await self.gptsettings(msg, self.gpt3_settings)
            return

        # user wants to modify GPT3 settings
        if usr_msg[0:6] == "gptset":
            ''' expect format: gptset [setting_name] [new_value]'''
            try:
                await self.gptset(usr_msg, self.gpt3_settings)
                await msg.channel.send("New parameter saved, current settings:")
                await self.gptsettings(msg, self.gpt3_settings)
            except Exception as e:
                await msg.channel.send("gptset: gptset [setting_name] [new_value]")
            return
        
        # modify GPT3repl settings
        if usr_msg[:10] == "gptreplset":
            ''' expect format: gptreplset [setting_name] [new_value]'''
            try:
                await self.gptset(usr_msg, GPT3_REPL_SETTINGS)
                await msg.channel.send("New parameter saved, current settings:")
                await self.gptsettings(msg, GPT3_REPL_SETTINGS)
            except Exception as e:
                await msg.channel.send("gptset: gptset [setting_name] [new_value]")
            return
        
        # show the current thread
        if usr_msg == "show thread":
            await self.send_msg_to_usr(msg, self.curr_convo_context)
            return

        # reset the current convo with the curr prompt context
        if usr_msg == "reset thread":
            await self.gpt_context_reset()
            await msg.channel.send(f"Thread Reset. Starting with (prompt) convo len = {len(self.curr_convo_context)}")
            return
        
        # check curr convo context length
        if usr_msg == "convo len":
            await msg.channel.send(len(self.curr_convo_context))
            return

        # Reminders based on a time
        if usr_msg[0:9] == "remind me":
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

                await self.send_msg_to_usr(msg, f"Reminder set for '{task}' in {time} {unit}.")
                await asyncio.sleep(remind_time)
                await self.send_msg_to_usr(msg, f"REMINDER: {task}")
            except Exception as e:
                await self.send_msg_to_usr(msg, "usage: remind me, [task_description], [time], [unit]")
            return

        await self.send_msg_to_usr(msg, "Type 'help' for a list of commands.")

    ############################## Main Function ##############################

    def run_discord_bot(self):
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
            # await self.gpt_context_reset()
            await self.gpt_prompt_initializer()

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
                await self.personal_assistant_block(msg, usr_msg)
                return

            ############################## StableDiffusion ##############################

            # enable stablediffusion if you have a gpu (did not write for cpu)
            if channel == self.stable_diffusion_channel:
                await self.send_msg_to_usr(msg, "Stable Diffusion is currently disabled.")
                # await self.gen_stable_diffusion(msg, usr_msg, chnl_num=1)
                return
            elif channel == self.waifu_diffusion_channel:
                await self.send_msg_to_usr(msg, "Stable Diffusion is currently disabled.")
                # await self.gen_stable_diffusion(msg, usr_msg, chnl_num=2)
                return

            ############################## GPT 3 REPL ##############################
            # enabled! confirmation is done through the same channel
            if channel == self.gpt3_repl_channel_name:
                
                await self.send_msg_to_usr(msg, "GPT3 REPL is currently disabled.")
                
                # if self.gpt3_repl_waiting_on_code_confirmation == False:
                #     self.gpt3_repl_waiting_on_code_confirmation = True
                #     # show user the code that was generated, want confirmation to run or not
                #     await msg.channel.send(await self.gen_gpt3_repl_step_one(usr_msg))
                # else:
                #     # we were waiting for code to be run
                #     self.gpt3_repl_waiting_on_code_confirmation = False
                #     # take user input and respond appropriately
                #     await msg.channel.send(await self.gen_gpt3_repl_step_two(usr_msg))
                return

            ############################## GPT 3 ##############################
            # if sent in GPT_CHANNEL3, send back a GPT3 response
            if channel == self.gpt3_channel_name:
                gpt_response = await self.gen_gpt3(usr_msg)
                formatted_response = {"role":self.chatgpt_name, "content":gpt_response}
                # update the str representation of msg log (not used for generations), to be displayed if asked in PA channel
                self.curr_convo_context += f"user: {usr_msg}\n"
                self.curr_convo_context += f"{self.chatgpt_name}: {gpt_response}\n"             
                self.gpt3_settings["messages"][0].append(formatted_response)
                await self.send_msg_to_usr(msg, gpt_response)
                return

        self.client.run(self.TOKEN)


if __name__ == "__main__":
    bot = BMO()
    bot.run_discord_bot()