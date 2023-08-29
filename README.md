# Discord Bot | Python 3

## What does this do?
- Convenience access to a local stable diffusion server (use automatic1111 with `--api` flag)
- Random ml stuff I throw together to learn what it's like integrating that stuff into a discord bot
- Convenience ui for GPT-3.5-turbo / GPT-4 from OpenAI
  Create your own random commands to improve your workflow if needed (I have some for prompt switching, saving threads, changing generation settings, etc.)

## Quick Setup (using pip/conda)
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