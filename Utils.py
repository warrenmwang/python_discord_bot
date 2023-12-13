import discord
import subprocess
import re
import os

# CONSTANTS
DISCORD_MSGLEN_CAP=2000

def run_bash(command : str) -> tuple[str,str]:
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = result.stdout
        stderr = result.stderr
        return stdout, stderr
    except Exception as e:
        return "", str(e)

async def send_msg_to_usr(msg : discord.message.Message, usr_msg : str) -> None: 
    '''
    in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
    the damn message (whether it be one or multiple messages)
    '''
    if not isinstance(usr_msg, str): return # do nothing if input is not a string

    diff = len(usr_msg)
    start = 0
    end = DISCORD_MSGLEN_CAP
    while diff > 0:
        await msg.channel.send(usr_msg[start:end])
        start = end
        end += DISCORD_MSGLEN_CAP
        diff -= DISCORD_MSGLEN_CAP

async def send_file_to_usr(msg : discord.message.Message, filePath : str) -> None:
    '''given the image path in the filesystem, send it to the author of the msg'''
    await msg.channel.send(file=discord.File(filePath))

def constructHelpMsg(d : dict)->str:
    '''Stringify the dictionary of commands and their descriptions'''
    help_str = '```'

    # initially construct the strings
    n = len(d.items())
    strings = [None for i in range(n)]
    for i, (k,v) in enumerate(d.items()):
        strings[i] = f'{k} - {v}'
    
    # Find the maximum length of the first part (before the dash)
    max_length = max(len(s.split('-')[0]) for s in strings)

    # Format and print the strings
    for s in strings:
        parts = s.split('-')
        formatted_string = "{:<{}} - {}".format(parts[0], max_length, parts[1].strip())
        help_str += f'{formatted_string}\n'
    help_str += '```'

    return help_str

def find_text_between_markers(text:str, start_marker:str="<START>", end_marker:str="<END>")->list[str]:
    '''Finds the text between the start and end markers in the given text'''
    pattern = re.escape(start_marker) + "(.*?)" + re.escape(end_marker)
    matches = re.findall(pattern, text, re.DOTALL)
    return matches

def delete_file(filepath:str)->None:
    '''Delete the file at the given filepath if it exists'''
    if os.path.exists(filepath):
        os.remove(filepath)