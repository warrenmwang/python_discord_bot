from __future__ import annotations
import discord
import re
import os
import fitz # PyMuPDF
import base64
import pytesseract # OCR engine
from PIL import Image
import io
import datetime
from typing import Callable, Any
import asyncio

import requests

DISCORD_MSGLEN_CAP=2000

class MyCustomException(Exception):
    def __init__(self, message):
        super().__init__(message)

class MyPDF:
    def __init__(self, url : str, embedded_text : str, ocr_text : str, raw_bytes : bytes):
        self.url = url
        self.embedded_text = embedded_text
        self.ocr_text = ocr_text
        self.raw_bytes = raw_bytes

'''
This acts as a common data structure for messages, which will allow me to 
decouple any internet messaging platform (e.g. Discord) and my own 
chatbot / personal assistant logic.

I realized I needed to decouple things and introduce this common data structure
after I wanted to introduce unit tests.
'''
class Message:
    '''
    Standard attachments format, as declared by myself, is going to be:
        dict[str -> list[str | object]]
    where the contents of the lists varies for key:
        1. texts: str
        2. images: base64 encoded str
        3. pdfs: MyPDF Class Objects

    Methods whose name begins with _test are used for unit testing
    '''
    def __init__(self, msgType: str = 'discord'):
        self.msgType = msgType

        self.content: str = ""
        self.author: discord.User | discord.Member | None = None
        self.discordMsg: discord.message.Message | None = None # obj needed for sending msgs back to the user
        self.attachments = None
 
    def _import_from_bare_text(self, msg: str) -> None:
        """
        Mutates the current instance and basically treats Message as a thin wrapper
        around a basic message type that's just a string.

        NOTE: without a discord message object, this cannot be used to send a message
        back to the user using discord interface.
        """
        self.msgType = "bare"
        self.content = msg

    def _import_from_discord(self, msg: discord.message.Message) -> None:
        """
        Imports the parts of the discord message that I actually use.
        Mutates the current instance.
        """

        self.content = msg.content # str
        self.author = msg.author   # discord.User | discord.Member
        self.discordMsg = msg      # discord.message.Message

        self.attachments = None

        if msg.attachments:
            self.attachments = {}
            self.attachments['texts'] = []
            self.attachments['images'] = []
            self.attachments['pdfs'] = []

            text_file_formats = ['.txt', '.c', '.cpp', '.py', '.ipynb', '.java', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.md']
            image_file_formats = ['.jpg', '.png', '.heic']

            for attachment in msg.attachments:
                # text files (plain text and code)
                # text files are stored as strings
                for file_format in text_file_formats:
                    if attachment.filename.endswith(file_format):
                        # Download the attachment
                        response = requests.get(attachment.url)
                        if response.status_code != 200: 
                            raise MyCustomException(f'request got status code: {response.status_code}')
                        file_content = response.text
                        self.attachments['texts'].append(file_content)

                # images (allow .jpg, .png, .heic)
                # images are stored as base64 encoded strings
                for image_format in image_file_formats:
                    if attachment.filename.endswith(image_format):
                        response = requests.get(attachment.url)
                        if response.status_code != 200:
                            raise MyCustomException(f'request got status code: {response.status_code}')
                        encodedImage = base64.b64encode(response.content).decode('utf-8')
                        self.attachments['images'].append(encodedImage)

                # pdfs (save as a MyPDF object)
                if attachment.filename.endswith('.pdf'):
                    response = requests.get(attachment.url)
                    if response.status_code != 200:
                        raise MyCustomException(f'request got status code: {response.status_code}')
                    embedded_text, ocr_text = read_pdf_from_memory(response.content)
                    mypdf = MyPDF(attachment.url, embedded_text, ocr_text, response.content) 
                    self.attachments['pdfs'].append(mypdf)

    @staticmethod
    async def send_msg_to_usr(msg: Message, usr_msg: str | None) -> None: 
        '''
        in case msg is longer than the DISCORD_MSGLEN_CAP, this abstracts away worrying about that and just sends 
        the damn message (whether it be one or multiple messages)
        '''
        if usr_msg is None: return

        if msg.msgType == 'discord':
            discordMsg = msg.discordMsg
            if discordMsg is None: raise Exception("Unexpected discordMsg is None.")
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

    @staticmethod
    async def send_img_to_usr(msg : Message, image : Image.Image) -> None:
        '''send the image as bytes '''
        if msg.msgType == 'discord':
            discordMsg = msg.discordMsg
            if discordMsg is None:
                raise Exception("Unexpected discordMsg is None.")
            with io.BytesIO() as image_binary:
                image.save(image_binary, format='PNG')
                image_binary.seek(0)
                await discordMsg.channel.send(file=discord.File(fp=image_binary, filename='image.png'))
        elif msg.msgType == 'test':
            print('Image sent')
        else: 
            print('Unknown msgType')

    @staticmethod
    def from_text(msg: str) -> Message:
        x = Message(msgType="bare")
        x._import_from_bare_text(msg)
        return x

    @staticmethod
    def from_discord(msg: discord.message.Message) -> Message:
        x = Message(msgType="discord")
        x._import_from_discord(msg)
        return x

def debug_log(s: object)->None:
    '''
    Print object s to log, where s could be a string or any object that can be viewed as a str.
    '''
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

async def send_as_file_attachment_to_usr(msg:Message, fileBytes:bytes, filename:str, fileExtension:str):
    '''
    Send as an file attachment the contents of fileBytes with name filename.fileExtension
    '''
    if msg.msgType == 'discord':
        discordMsg = msg.discordMsg
        if discordMsg is None: raise Exception("Unexpected discordMsg is None.")
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
    strings = ['' for _ in range(n)]
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
