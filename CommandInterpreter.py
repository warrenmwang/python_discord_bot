from Utils import send_msg_to_usr
import discord
import asyncio

class CommandInterpreter:
    '''
    Tries to interpret inputs as commands and perform the action requested
    If the action is not found to be a hard-coded command, reply the "command" or gpt response to user.
    '''
    def __init__(self):
        pass

    async def main(self, msg : discord.message.Message, command : str) -> None:
        '''
        tries to map the usr_msg to a functionality
        at this point, chatgpt should've interpretted any user command into one of these formats
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
    
        # not a hard coded command, send the gpt response to user
        await send_msg_to_usr(msg, command)