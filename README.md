# Discord Bot | Python 3.11.0
*last updated 02/11/2023*

Video Demo: https://youtu.be/BwTqOWEXlc0 [created: 12/22/2022]

## How to use
### Docker
You can run this using docker, although my workaround is to wrap an entire anaconda3 installation, then create the env inside the container, then use that env's python binary to run the source files copied over; this is pretty dumb, and in the future I'll try to make this more lightweight. Being at the root of the dir, example:

0. If you're building your own container you will need your own anaconda install script, which you can download here: [link](https://repo.anaconda.com/archive/Anaconda3-2022.10-Linux-x86_64.sh)
1. Create your `private` folder with your prompt files
2. Setup your `.env` variables (openai token, names of stuff, etc.)
3. Run the docker commands, fill with your own info:
```
docker build -t pydisc .
docker run --env-file .env -v /home/wang/code/git/python_discord_bot/private:/app/private pydisc 
```

Or you can use my [image](https://hub.docker.com/r/warrenwangg/pydisc)


### Anaconda 
Originally written to be used in a `conda` environment making use of notable packages discord and openai.

All packages can be found in `environment.yml`. Using conda, you can create the environment immediately: <br>
`conda env create -f environment.yml`

### Stable Diffusion Setup
You can use whatever fork of stable diffusion you want; I am using [InvokeAI](https://github.com/invoke-ai)'s. 


### Manual (using up conda)
1. Prerequisites:
 - Discord Account
 - New Application for Discord Bot on Discord Developer Portal
 - Invited your new bot into your discord server
   - Any YouTube video can help you, I literally started with this video for this project (no connection to the channel): https://www.youtube.com/watch?v=hoDLj0IzZMU
2. Clone/fork this repo
3. `cd` into the repo
4. `conda env create -f environment.yml`
5. `conda activate discord_bot`
6. Create a `.env` file and put all your information in there
7. `python ./main.py`
8. Start talking!

## Other Notes
- `eval()` is used in the calculator and this can be exploited (e.g. `__import__('os').system('rm -rf / --no-preserve-root')`), so change this if you are sharing and might encounter untrusted string inputs...
- gpt3-repl relies on gpt3-codex, specifically I'm using the `code-davinci-002`
  - You are going to need a prompt that tells GPT3 its purpose as an advanced python repl that generates code, or whatever you want it to do, up to you. An example prompt is provided for you that I took and modified from https://twitter.com/goodside at sometime long ago.
