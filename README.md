# ChatGPT Discord Bot

## Overview
A powerful Discord bot that integrates OpenAI's latest models (GPT-4, GPT-4 Vision, DALL-E 3) to provide advanced chat capabilities and AI-powered features in your Discord server. The bot supports:

- Text conversations with GPT-4 and other OpenAI models
- Image analysis and generation using GPT-4 Vision and DALL-E 3
- Document processing (PDF, TXT) with built-in memory
- RAG (Retrieval-Augmented Generation) capabilities using VectorDB
- Persistent conversation history
- Custom prompt management

## Key Features
- **Multiple AI Models**: Support for various OpenAI models including gpt-4-1106-preview and gpt-4-vision-preview
- **Document Processing**: Upload and analyze PDF and TXT files
- **Long-term Memory**: Store and search through documents using VectorDB
- **Image Capabilities**: Analyze images with GPT-4 Vision and generate images with DALL-E 3
- **Context Management**: Maintain conversation context within sessions
- **Custom Commands**: Accessible via the '!' prefix

## Commands
All commands start with the prefix `!`. Here are some key commands:

### General Commands
- `help` - Show this message
- `remind me` - Set a reminder that will ping you in a specified amount of time
  - Format: `[remind me], [description], [numerical value], [time unit (s,m,h)]`
- `draw` - Generate images using DALL-E 3
  - Format: `[draw]; [prompt]`

### Vector Database Commands
- `chroma status` - Get the status of the Chroma Vector DB for ChatGPT memory
- `upload` - Upload a text document (.pdf or .txt) to be stored into the Vector DB
- `query` - Query documents in the Vector DB to talk with ChatGPT
  - Format: `[query] [prompt]`
- `_attachTextFile` - Command for GPT interpreter
  - Format: `_attachTextFile [commentary] [code]`
  - Use `<CODESTART>` `<CODEEND>` for code segments
  - Use `<COMMENTSTART>` `<COMMENTEND>` for commentary

### GPT Commands
- `help (h)` - Display this message
- `convo len (cl)` - Show current GPT context length
- `reset thread (rt)` - Reset GPT context length
- `show thread (st)` - Show the entire current conversation context
- `gptsettings` - Show the current GPT settings
- `gptset` - Modify GPT settings
  - Format: `gptset [setting_name] [new_value]`
- `current prompt (cp)` - Get the current prompt name
- `change prompt (chp)` - Change to a new prompt
  - Format: `change prompt, [new prompt name]`
- `list prompts (lp)` - List available prompts
- `list models (lm)` - List available GPT models
- `modify prompts` - Modify the prompts for GPT
- `save thread` - Save the current GPT thread to a file
- `show old threads` - Show saved threads
- `load thread` - Load a GPT thread from file
  - Format: `load thread, [unique id]`
- `delete thread` - Delete a GPT thread
  - Format: `delete thread, [unique id]`
- `current model (cm)` - Show the current GPT model
- `swap` - Switch between models (gpt-4-0125-preview, gpt-4-vision-preview)


## Getting Started

### Docker
The easiest way to get started.
1. Ensure variables are in your `.env` file.
2. Source your env file to load the variables in the current shell's env.
3. Run `docker compose up`. This will run the application and keep the shell attached to the 
container's logs. If you want to run this detached, run `docker compose up -d`.

To stop the running containerized application, run `docker compose down`.
Note the default docker compose configuration creates a persistent volume that will store your RAG files, custom prompts, 
and any saved threads to disk. 
If you want to remove the persisted data in the named volume defined in the `docker-compose.yml`
run `docker compose down -v`.

### Running with a python environment
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
    conda create -n my_discord_bot python=3.12
    conda activate my_discord_bot
    pip install -r requirements.txt
    ```
  Yes use this specific python version.
5. Create a `.env` file and put all your API keys and other info in there
6. Run with `python ./main.py`.

## Unit Tests

To run unit tests
```
python -m unittest discover -v -s ./tests
```
