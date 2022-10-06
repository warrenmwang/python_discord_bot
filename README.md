# Discord Bot | Python 3.10.4
*last updated 10/06/2022*

Originally written to be used in a `conda` environment making use of notable packages discord and openai.

All packages can be found in `package-list.txt`. Using conda, you can create the environment immediately: <br>


If you are to use it, you will need to create your own `.env` file in the same directory will all of your own tokens and strings.

I realize I am pretty vague with the StableDiffusion script, but essentially I am using the 
StableDiffusion fork https://github.com/invoke-ai/InvokeAI. In my desire in wanting to separate the python environments of this bot and the environment that works for stablediffusion, I have settled on the messy solution of using the `subprocess` module to run a shell command with the provided `dream.py` script in the forked repo. The shell command is along the lines of 

`python dream.py --model [model_weights] --config [config_file] --from_file prompt_file.txt`

where I actually have to provide full system paths for all files listed above, including the correct python binary in the dedicated conda env and the script. 

## How to use
0. Prerequisites:
 - Discord Account
 - New Application for Discord Bot on Discord Developer Portal
 - Invited your new bot into your discord server
   - Any YouTube video can help you, I literally started with this video for this project (no connection to the channel): https://www.youtube.com/watch?v=hoDLj0IzZMU

1. Clone/fork this repo
2. `cd` into the repo
3. `conda create --name <a_env_name> --file package-list.txt`
5. Create a `.env` file and put all your information in there
6. (optional) Edit `quotes.txt` and `responses.py` to whatever you want...personalize it for yourself.
4. `python ./main.py`
5. Start talking!