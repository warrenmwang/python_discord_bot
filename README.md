# ChatGPT Discord Bot 

## What does this do?
This is a Discord chat interface for ChatGPT API models (e.g. gpt-4-1106-preview, gpt-4-vision-preview, dalle3, etc.) from OpenAI. 
You can talk directly with your text, pdf, and image files by loading them directly in the current session context or by uploading them 
(currently only pdf and txt files are supported for vector db) into the VectorDB for long-term storage and more extensive searching 
amongst personal out-of-ChatGPT training data.

## Prefix Commands
Current Commands accessible with command prefix `!`

Personal Assistant Commands:
```
help             -- show this message
remind me        -- format is `[remind me], [description], [numerical value], [time unit (s,m,h)]`; sets a reminder that will ping you in a specified amount of time
draw             -- format is `[draw]; [prompt]` and it allows you to draw images using Dalle API from OpenAI, default is using Dalle3
upload           -- (vector db) upload a text document (.pdf or .txt) to be stored into the Vector DB
query            -- (vector db) query documents in the Vector DB to be used to talk with w/ ChatGPT; format is `[query] [prompt]`
_attachTextFile  -- Command only for GPT interpreter. Wrap any long code segments in <CODESTART> <CODEEND> and any commentary in <COMMENTSTART> <COMMENTEND>. DO NOT PUT EVERYTHING INTO A SINGLE LINE, use newlines, tabs, normal code formatting. format is `_attachTextFile [commentary] [code]` where each section can span multiple lines.
```

ChatGPT commands:
```
help (h)             -- display this message
convo len (cl)       -- show current gpt context length
reset thread (rt)    -- reset gpt context length
show thread (st)     -- show the entire current convo context
gptsettings          -- show the current gpt settings
gptset               -- format is `gptset [setting_name] [new_value]` modify gpt settings
current prompt (cp)  -- get the current prompt name
change prompt (chp)  -- format `change prompt, [new prompt name]`
list prompts (lp)    -- list the available prompts for gpt
list models (lm)     -- list the available gpt models
modify prompts       -- modify the prompts for gpt
save thread          -- save the current gptX thread to a file
show old threads     -- show the old threads that have been saved
load thread          -- format `load thread, [unique id]` load a gptX thread from a file
delete thread        -- format `delete thread, [unique id]` delete a gptX thread from a file
current model (cm)   -- show the current gpt model
swap                 -- hotswap btwn models: (['gpt-4-0125-preview', 'gpt-4-vision-preview'])
```

## Video Demonstration
[![youtube video demonstration](https://img.youtube.com/vi/KFOIwvz3dY4/0.jpg)](https://www.youtube.com/watch?v=KFOIwvz3dY4)
> Note video demonstrates usage of stable-diffusion, which is no longer a supported feature. A new video demo is on its way.

## Quick setup (using pip/conda)
1. Prerequisites:
    - Get Discord Bot Token
      - New Application for Discord Bot on Discord Developer Portal
      - Invited your new bot into your discord server
        - Help: [video](https://www.youtube.com/watch?v=hoDLj0IzZMU) 
    - Get OpenAI API Key
      - You'll need to create an account with [OpenAI](https://openai.com/) and create an API key, put that in the `.env` file.
    - If you want to pass PDFs into the bot, you will need to have the `tesseract` binary
    in your path. Instructions for installing it can be found [here](https://github.com/tesseract-ocr/tesseract?tab=readme-ov-file#installing-tesseract).

2. Clone/fork this repo
3. `cd` into the repo
4. Python Environment Setup:
    ```
    conda create -n my_discord_bot python=3.11.3
    conda activate my_discord_bot
    pip install -r requirements.txt
    ```
    > NOTE: I'm arbitrarily using `python 3.11.3`. Probably any `3.11.X` will work. 
5. Create a `.env` file and put all your API keys and other info in there
6. Run with `python ./main.py`. Here is the command line argument parser's help string for optional flags you can pass in:
    ```
    usage: main.py [-h] [-d] [-r]

    options:
      -h, --help   show this help message and exit
      -d, --debug  enable debug printing
      -r, --rag    enable RAG for Personal Assistant
    ```

## Unit Tests

To run unit tests
```
python -m unittest discover -v -s ./tests
```