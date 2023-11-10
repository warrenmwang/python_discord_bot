import os
from Utils import send_msg_to_usr
from ChatGPT import Dalle
import discord
import asyncio
from Utils import send_img_to_usr

class CommandInterpreter:
    '''
    Tries to interpret inputs as commands and perform the action requested
    If the action is not found to be a hard-coded command, reply the "command" or gpt response to user.
    '''
    def __init__(self, help_str : str, debug : bool = False):
        self.DEBUG = debug
        self.help_str = help_str
        self.dalle = Dalle(debug)
        self.dalle_output_path = os.getenv("DALLE_OUTPUT_PATH")

    async def main(self, msg : discord.message.Message, command : str) -> None:
        '''
        tries to map the usr_msg to a functionality
        at this point, chatgpt should've interpretted any user command into one of these formats

        Assumes: command does NOT have a command prefix symbol.
        '''
        if command[0:9] == "remind me":
            try:
                tmp = list(map(str.strip, command.split(',')))
                task, time, unit = tmp[1], float(tmp[2]), tmp[3]
                if unit == "s":
                    remind_time = time
                elif unit == "m":
                    remind_time = time * 60
                elif unit == "h":
                    remind_time = time * 3600
                elif unit == "d":
                    remind_time = time * 86400
                else:
                    await msg.channel.send("only time units implemented: s, m, h, d")
                    return

                await send_msg_to_usr(msg, f"Reminder set for '{task}' in {time} {unit}.")
                await asyncio.sleep(remind_time)
                await send_msg_to_usr(msg, f"REMINDER: {task}")
            except Exception as e:
                await send_msg_to_usr(msg, "usage: remind me, [task_description], [time], [unit]")
            return

        if command == "help":
            return self.help_str

        if command[0:4] == "draw":
            # draw images using dalle api
            # for now, keep things simple with just the word draw semicolon and then the prompt
            prompt = command.split(";")[1].strip() # parse prompt out of command, assumes NO SEMICOLONS in prompt lol
            await send_msg_to_usr(msg, f"Creating an image of `{prompt}`")
            image = await self.dalle.main(prompt)
            image.save(self.dalle_output_path)
            await send_img_to_usr(msg, self.dalle_output_path)
            return 
    
        return "Uknown command."
