"""
This acts as a common data structure for messages, which will allow me to 
decouple any internet messaging platform (e.g. Discord) and my own 
chatbot / personal assistant logic.

I realized I needed to decouple things and introduce this common data structure
after I wanted to introduce unit tests.
"""
# for importing code from Utils
import sys
sys.path.append('..')

import discord
import requests
import base64
from Utils import read_pdf_from_memory


class MyCustomException(Exception):
    def __init__(self, message):
        super().__init__(message)

class MyPDF:
    def __init__(self, url : str, embedded_text : str, ocr_text : str, raw_bytes : bytes):
        self.url = url
        self.embedded_text = embedded_text
        self.ocr_text = ocr_text
        self.raw_bytes = raw_bytes

class Message:
    def __init__(self):
        pass

    def importFromDiscord(self, msg : discord.message.Message) -> None:
        '''Imports the parts of the discord message that I actually use.'''

        self.content = msg.content # str
        self.author = msg.author   # discord.User | discord.Member

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
                    embedded_text, ocr_text = read_pdf_from_memory(response.content)
                    mypdf = MyPDF(attachment.url, embedded_text, ocr_text, response.content) 
                    self.attachments['pdfs'].append(mypdf)
        