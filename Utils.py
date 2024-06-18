from __future__ import annotations
import discord
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

async def send_msg_to_usr(msg : Message, usr_msg : str) -> None: 
    '''
    in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
    the damn message (whether it be one or multiple messages)
    '''
    if not isinstance(usr_msg, str): return # do nothing if input is not a string

    if msg.msgType == 'discord':
        discordMsg = msg.discordMsg
        diff = len(usr_msg)
        start = 0
        end = DISCORD_MSGLEN_CAP
        while diff > 0:
            await discordMsg.channel.send(usr_msg[start:end])
            start = end
            end += DISCORD_MSGLEN_CAP
            diff -= DISCORD_MSGLEN_CAP
    elif msg.msgType == 'test':
        print(usr_msg)
    else:
        print('Unknown msgType')

async def send_img_to_usr(msg : Message, image : Image) -> None:
    '''send the image as bytes '''
    if msg.msgType == 'discord':
        discordMsg = msg.discordMsg
        with io.BytesIO() as image_binary:
            image.save(image_binary, format='PNG')
            image_binary.seek(0)
            await discordMsg.channel.send(file=discord.File(fp=image_binary, filename='image.png'))
    elif msg.msgType == 'test':
        print('Image sent')
    else: 
        print('Unknown msgType')

async def send_as_file_attachment_to_usr(msg:Message, fileBytes:bytes, filename:str, fileExtension:str):
    '''
    Send as an file attachment the contents of fileBytes with name filename.fileExtension
    '''
    if msg.msgType == 'discord':
        discordMsg = msg.discordMsg
        completeFilename = f"{filename}.{fileExtension}"
        fileToSend = discord.File(fp=io.BytesIO(fileBytes), filename=completeFilename)
        await discordMsg.channel.send(file=fileToSend)
    elif msg.msgType == 'test':
        print(f"File sent: {filename}.{fileExtension}")
    else:
        print('Unknown msgType')

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
