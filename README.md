# Jarvis discord bot
Honestly I'm just trying to see what it's like to make a discord bot with an amalgamation of random functionalities and seeing if it's useful. "One bot to rule them all" kind of feel.

## What does this do?
- Convenience access to a local stable diffusion server (use automatic1111 with `--api` flag)
- Random ml stuff I throw together to learn what it's like integrating that stuff into a discord bot
- Convenience ui for GPT-3.5-turbo / GPT-4 from OpenAI
  Create your own random commands to improve your workflow if needed (I have some for prompt switching, saving threads, changing generation settings, etc.)

## Quick setup (using pip/conda)
1. Prerequisites:
 - Discord Account
 - New Application for Discord Bot on Discord Developer Portal
 - Invited your new bot into your discord server
   - Any YouTube video can help you, I literally started with this [video](https://www.youtube.com/watch?v=hoDLj0IzZMU) for this project
2. Clone/fork this repo
3. `cd` into the repo
4. `pip install -r requirements`
6. Create a `.env` file and put all your information in there
7. `python ./main.py`
8. Start talking!
9. Well, you'll need other stuff if you want to run the ml stuff, you can figure that out :)

## The submodules
### [Stable Diffusion Webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
Git submodules should get the repo for you, and it should just work because it runs `webui.sh` with some command line params that creates your `venv` when you run it the first time. All times after the first run should be fast. I decided to just run it in a `tmux` session, but maybe that's bad design but hey the linux platform has so many nice tools, why not use them amirite.

### [nanoGPT](https://github.com/karpathy/nanoGPT/tree/master)
Look at the README in that repo to train up whatever parrot mini transformer model to replicate the text of and modify the hard-coded shell command to point to the python installation with the packages needed to run that -- that would be a thing you have to do :)