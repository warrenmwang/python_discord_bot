# ChatGPT Discord Bot 

## What does this do?
This is a Discord chat interface for ChatGPT API models (e.g. gpt-4-1106-preview, gpt-4-vision-preview, dalle3, etc.) from OpenAI. 
You can talk directly with your text, pdf, and image files by loading them directly in the current session context or by uploading them 
(currently only pdf and txt files are supported for vector db) into the VectorDB for long-term storage and more extensive searching 
amongst personal out-of-ChatGPT training data.

## Prefix Commands
Current Commands accessible with command prefix `!`

## Video Demonstration
[![youtube video demonstration](https://img.youtube.com/vi/KFOIwvz3dY4/0.jpg)](https://www.youtube.com/watch?v=KFOIwvz3dY4)
> Note video demonstrates usage of stable-diffusion, which is no longer a supported feature. A new video demo is on its way.

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
    conda create -n my_discord_bot python=3.12.4
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