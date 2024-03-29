from __future__ import annotations
import discord
import subprocess
import re
import os
import fitz # PyMuPDF
import pytesseract # OCR engine
from PIL import Image
import io
import datetime
from typing import Callable, Any
import asyncio

DISCORD_MSGLEN_CAP=2000

def debug_log(s: str)->None:
    '''print string s in debug logging format'''
    # Get the current terminal width
    terminal_width = os.get_terminal_size().columns
    
    # Prepare the debug message
    debug_message = f"DEBUG: {s}"
    
    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate the number of spaces needed to align the timestamp to the right
    spaces_needed = terminal_width - len(debug_message) - len(timestamp) - 1
    
    # Print the debug message with the timestamp aligned to the right
    print(f"{debug_message}{' ' * spaces_needed}{timestamp}")

def run_bash(command : str) -> tuple[str,str]:
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = result.stdout
        stderr = result.stderr
        return stdout, stderr
    except Exception as e:
        return "", str(e)

async def send_msg_to_usr(msg : Message, usr_msg : str) -> None: 
    '''
    in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
    the damn message (whether it be one or multiple messages)
    '''
    if not isinstance(usr_msg, str): return # do nothing if input is not a string

    discordMsg = msg.discordMsg
    diff = len(usr_msg)
    start = 0
    end = DISCORD_MSGLEN_CAP
    while diff > 0:
        await discordMsg.channel.send(usr_msg[start:end])
        start = end
        end += DISCORD_MSGLEN_CAP
        diff -= DISCORD_MSGLEN_CAP

async def send_img_to_usr(msg : Message, image : Image) -> None:
    '''send the image as bytes '''
    discordMsg = msg.discordMsg
    with io.BytesIO() as image_binary:
        image.save(image_binary, format='PNG')
        image_binary.seek(0)
        await discordMsg.channel.send(file=discord.File(fp=image_binary, filename='image.png'))

# TODO: i am going to have to depreciate this function and send any files as bytes in memory to the user
# rather than introducing a file system dependency
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
        strings[i] = f'{k} -- {v}'
    
    # Find the maximum length of the first part (before the dash)
    max_length = max(len(s.split('--')[0]) for s in strings)

    # Format and print the strings
    for s in strings:
        parts = s.split('--')
        formatted_string = "{:<{}} -- {}".format(parts[0], max_length, parts[1].strip())
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

def read_pdf_from_memory(pdf_bytes: bytes) -> tuple[str, str]:
    '''Reads the PDF from bytes and returns both the embedded text and the OCR'd text separately'''
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    all_embedded_text = ""
    all_ocr_text = ""
    for page in pdf_doc:
        # Embedded text
        embedded_text = page.get_text()
        all_embedded_text += embedded_text

        # OCR
        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes()))
        ocr_text = pytesseract.image_to_string(img)
        all_ocr_text += ocr_text

    return all_embedded_text, all_ocr_text

# TODO: delete this function, once replaced all occurences with the new one.
def read_pdf(file_path: str)->tuple[str,str]:
    '''Reads the pdf at the given file path and returns both the embedded text and the OCR'd text seperately'''
    pdf_doc = fitz.open(file_path)

    all_embedded_text = ""
    all_ocr_text = ""
    for i in range(len(pdf_doc)):
        page = pdf_doc[i]
        # embedded text
        embedded_text = page.get_text()
        all_embedded_text += embedded_text
        # ocr
        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes()))
        ocr_text = pytesseract.image_to_string(img)
        all_ocr_text += ocr_text

    return all_embedded_text, all_ocr_text

async def runTryExcept(foo : Callable, **kwargs) -> Any:
    # given a function and the input params, 
    # run the function with the given inputs params into it
    # and return the error message as a string if there is one
    # otherwise, return whatever the function returns
    try:
        if asyncio.iscoroutinefunction(foo):
            return await foo(**kwargs)
        else:
            return foo(**kwargs)
    except Exception as e:
        return f'Encountered Error: {str(e)}'
