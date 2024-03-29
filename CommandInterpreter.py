import os
from Utils import send_msg_to_usr
from ChatGPT import Dalle, ChatGPT
import discord
import asyncio
from Utils import send_file_to_usr, find_text_between_markers, delete_file, read_pdf, debug_log, send_img_to_usr
from VectorDB import VectorDB
import requests

class CommandInterpreter:
    '''
    Tries to interpret inputs as commands and perform the action requested
    If the action is not found to be a hard-coded command, reply the "command" or gpt response to user.
    '''
    def __init__(self, help_str : str, gpt_interpreter : ChatGPT = None, debug : bool = False, enableRAG : bool = False):
        '''
        an option to enable/disable RAG bc it is more computationally expensive, and i dont want to spend money in the cloud
        '''
        self.DEBUG = debug
        self.help_str = help_str
        self.tmp_dir = "./tmp"
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # Dalle
        self.dalle = Dalle(debug)

        # VectorDB for RAG
        self.enableRAG = enableRAG
        if self.enableRAG:
            self.gpt_interpreter = gpt_interpreter
            chroma_data_path = "chroma_data/"
            embed_model = "all-MiniLM-L6-v2"
            collection_name = "main"
            self.vectorDB = VectorDB(chroma_data_path, embed_model, collection_name)
        else:
            if debug: debug_log("CommandInterpreter: RAG is not enabled.")

    async def main(self, msg : discord.message.Message, command : str) -> None:
        '''
        tries to map the usr_msg to a functionality
        at this point, chatgpt should've interpretted any user command into one of these formats

        If return anything other than None, then it is a response to the user (likely an error message)

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
            try:
                prompt = command.split(";")
                if len(prompt) != 2: return "Invalid draw command."
                prompt = prompt[1].strip()
                if len(prompt) == 0: return "Cannot draw empty prompt."
                await send_msg_to_usr(msg, f"Creating an image of `{prompt}`")
                await send_img_to_usr(msg, await self.dalle.main(prompt))
                return 
            except Exception as error:
                return error

        ### Vector DB
        if command == "upload":
            if not self.enableRAG: return "RAG is not enabled. Upload cannot be performed."
            if msg.attachments:
                for attachment in msg.attachments:
                    # pdfs (grab embedded and ocr text -- use both in context)
                    if attachment.filename.endswith('.pdf'):
                        response = requests.get(attachment.url) # download pdf
                        pdf_file = f"{self.tmp_dir}/tmp.pdf"
                        with open(pdf_file, "wb") as f:
                            f.write(response.content)
                        embedded_text, ocr_text = read_pdf(pdf_file)
                        delete_file(pdf_file)
                        document = "\nPDF CONTENTS:\n" + embedded_text + "\nOCR CONTENTS:\n" + ocr_text
                        self.vectorDB.upload(document)
                    
                    # text files
                    if attachment.filename.endswith('.txt'):
                        document = requests.get(attachment.url).text
                        self.vectorDB.upload(document)

            return "Upload complete."

        if command[:5] == "query":
            if not self.enableRAG: return "RAG is not enabled. Query cannot be performed."
            # get context from db
            db_query_prompt = command[6:]
            db_context = self.vectorDB.query(db_query_prompt)[0]
            if self.DEBUG: debug_log(f"Vector db retrieved: {db_context}")

            # TODO: how much of the context should be provided (consider if document is a 20 page paper...)
            # pass to gpt
            prompt = f"ORIGINAL USER QUERY:{command[6:]}\nVECTOR DB CONTEXT:{db_context}\nRESPONSE:"
            gpt_response = await self.gpt_interpreter.mainNoAttachments(prompt)

            return gpt_response
            

        #### "HIDDEN COMMANDS"
    
        if command[0:15] == '_attachTextFile':
            # attaches text file(s) for the contents in between the markers <CODESTART> and <CODEEND>
            codeFilePath = "/tmp/discord_code_tmp.txt"
            code = find_text_between_markers(command, start_marker="<CODESTART>", end_marker="<CODEEND>")
            for c in code:
                with open(codeFilePath, "w") as file:
                    file.write(c)
                await send_file_to_usr(msg, codeFilePath)
            delete_file(codeFilePath)
            # returns any commentary denoted by <COMMENTSTART> and <COMMENTEND>
            comment = find_text_between_markers(command, start_marker="<COMMENTSTART>", end_marker="<COMMENTEND>")
            return "\n".join(comment)+"End of Request."

        return "Unknown command."
