from GenerativeAI import LLM_Controller
from CommandInterpreter import CommandInterpreter
from Utils import constructHelpMsg, Message

class PersonalAssistant:
    '''
    Personal assistant, interprets hard-coded and arbitrary user commands/messages
    '''
    def __init__(self):
        self.DEBUG = False
        self.personal_assistant_state = None
        self.personal_assistant_modify_prompts_state = None
        self.personal_assistant_modify_prompts_buff = []
        self.personal_assistant_commands = {
            "help": "show this message",
            "remind me": "format is `[remind me], [description], [numerical value], [time unit (s,m,h)]`; sets a reminder that will ping you in a specified amount of time",
            'draw': "format is `[draw]; [prompt]` and it allows you to draw images using Dalle API from OpenAI, default is using Dalle3",
            'chroma status': "get the status of the Chroma Vector DB for ChatGPT memory",
            'upload': '(vector db) upload a text document (.pdf or .txt) to be stored into the Vector DB',
            'query': '(vector db) query documents in the Vector DB to be used to talk with w/ ChatGPT; format is `[query] [prompt]`',
            '_attachTextFile': "Command only for GPT interpreter. Wrap any long code segments in <CODESTART> <CODEEND> and any commentary in <COMMENTSTART> <COMMENTEND>. DO NOT PUT EVERYTHING INTO A SINGLE LINE, use newlines, tabs, normal code formatting. format is `_attachTextFile [commentary] [code]` where each section can span multiple lines."
        }
        self.personal_assistant_command_options = self.personal_assistant_commands.keys()
        self.help_str = constructHelpMsg(self.personal_assistant_commands)
        self.cmd_prefix = "!"

        self.gpt_interpreter = LLM_Controller()

        self.command_interpreter = CommandInterpreter(help_str=self.help_str, 
                                                      gpt_interpreter=self.gpt_interpreter)

        self.setup_complete = False

    async def main(self, msg : Message) -> str | None:
        '''
        Handles the user input for one of the hard-coded commands, if unable to find a hard-coded command to fulfill request
        will use one of the LLM interpreters available (for now local LLAMA or chatgpt)

        Priority Order
        1. Hard coded commands
        2. GPT Interpreter Settings
        2. ChatGPT Response -> Try hard coded, otherwise send back to user
        '''
        if not self.setup_complete:
            prompt = "You are a personal assistant who interprets users requests into either one of the hard coded commands that you will learn about in a second or respond accordingly to the best of your knowledge."
            prompt += f"The hard-coded commands are: {str(self.personal_assistant_commands)}"
            prompt += f"If you recognize what the user wants, output a single line that will activate the hard coded command prefixed with {self.cmd_prefix} and nothing else. Otherwise, talk."
            await self.gpt_interpreter.main(Message.from_text(f"!_add_and_set_prompt<SEP>personal_assistant<SEP>{prompt}<SEP>True"))
            self.setup_complete = True

        usr_msg = msg.content

        # list all the commands available
        if usr_msg == f"{self.cmd_prefix}help":
            pa_cmds = f"PA Commands:\n{self.help_str}"
            gpt_cmds = f"GPT Commands:\n{await self.gpt_interpreter.main(msg)}"
            await Message.send_msg_to_usr(msg, pa_cmds)
            await Message.send_msg_to_usr(msg, gpt_cmds)
            return None

        # hard coded commands
        if usr_msg[0] == self.cmd_prefix:
            x = await self.command_interpreter.main(msg, usr_msg[1:])
            if x != 'Unknown command.':
                return x
            # see if it's a gpt modify command
            gpt_response = await self.gpt_interpreter.main(msg)
            if gpt_response != "Unknown command.":
                return gpt_response

        # let gpt interpret
        gpt_response = await self.gpt_interpreter.main(msg)
        if gpt_response[0] == self.cmd_prefix:
            return await self.command_interpreter.main(msg, gpt_response[1:])
        return gpt_response
