import discord
import os
from ChatGPT import ChatGPT
from CommandInterpreter import CommandInterpreter
from Utils import send_msg_to_usr, constructHelpMsg
from Message import Message

class PersonalAssistant:
    '''
    Personal assistant, interprets hard-coded and arbitrary user commands/messages
    '''
    def __init__(self, debug:bool=False, enableRAG:bool=False):
        self.DEBUG = debug
        self.personal_assistant_channel = os.getenv('PERSONAL_ASSISTANT_CHANNEL')
        assert self.personal_assistant_channel != '', "PERSONAL_ASSISTANT_CHANNEL environment variable not set."
        self.personal_assistant_state = None
        self.personal_assistant_modify_prompts_state = None
        self.personal_assistant_modify_prompts_buff = []
        self.personal_assistant_commands = {
            "help": "show this message",
            # "pa_llama": "toggle the use of a llama model to interpret an unknown command (huge WIP)",
            "remind me": "format is `[remind me], [description], [numerical value], [time unit (s,m,h)]`; sets a reminder that will ping you in a specified amount of time",
            'draw': "format is `[draw]; [prompt]` and it allows you to draw images using Dalle API from OpenAI, default is using Dalle3",
            'upload': '(vector db) upload a text document (.pdf or .txt) to be stored into the Vector DB',
            'query': '(vector db) query documents in the Vector DB to be used to talk with w/ ChatGPT; format is `[query] [prompt]`',
            '_attachTextFile': "Command only for GPT interpreter. Wrap any long code segments in <CODESTART> <CODEEND> and any commentary in <COMMENTSTART> <COMMENTEND>. DO NOT PUT EVERYTHING INTO A SINGLE LINE, use newlines, tabs, normal code formatting. format is `_attachTextFile [commentary] [code]` where each section can span multiple lines."
        }
        self.personal_assistant_command_options = self.personal_assistant_commands.keys()
        self.help_str = constructHelpMsg(self.personal_assistant_commands)
        self.cmd_prefix = "!"

        self.gpt_interpreter = ChatGPT(debug)
        prompt = "You are a personal assistant who interprets users requests into either one of the hard coded commands that you will learn about in a second or respond accordingly to the best of your knowledge."
        prompt += f"The hard-coded commands are: {str(self.personal_assistant_commands)}"
        prompt += f"If you recognize what the user wants, output a single line that will activate the hard coded command prefixed with {self.cmd_prefix} and nothing else. Otherwise, talk."
        self.gpt_interpreter._setPrompt(prompt)

        self.command_interpreter = CommandInterpreter(help_str=self.help_str, 
                                                      gpt_interpreter=self.gpt_interpreter,
                                                      debug=debug, 
                                                      enableRAG=enableRAG)

    async def main(self, msg : Message) -> str:
        '''
        Handles the user input for one of the hard-coded commands, if unable to find a hard-coded command to fulfill request
        will use one of the LLM interpreters available (for now local LLAMA or chatgpt)

        Priority Order
        1. Hard coded commands
        2. GPT Interpreter Settings
        2. ChatGPT Response -> Try hard coded, otherwise send back to user
        '''
        usr_msg = msg.content

        # handle personal assistant state (if any)
        if self.personal_assistant_state == "modify prompts":
            return await self._pa_modify_prompts(self, usr_msg)

        # list all the commands available
        if usr_msg == f"{self.cmd_prefix}help":
            pa_cmds = f"PA Commands:\n{self.help_str}"
            gpt_cmds = f"GPT Commands:\n{await self.gpt_interpreter.main(msg)}"
            await send_msg_to_usr(msg, pa_cmds)
            await send_msg_to_usr(msg, gpt_cmds)
            return None

        # hard coded commands
        if usr_msg[0] == self.cmd_prefix:
            x = await self.command_interpreter.main(msg, usr_msg[1:])
            if x != 'Unknown command.': return x
            # see if it's a gpt modify command
            gpt_response = await self.gpt_interpreter.main(msg)
            if gpt_response != "Unknown command.":
                return gpt_response

        # let gpt interpret
        gpt_response = await self.gpt_interpreter.main(msg)
        if gpt_response[0] == self.cmd_prefix:
            return await self.command_interpreter.main(msg, gpt_response[1:])
        return gpt_response
