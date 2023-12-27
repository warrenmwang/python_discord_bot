# AI-Powered Discord ChatBot
"One bot to rule them all" kind of feel.

## What does this do?
- Discord chat interface for ChatGPT API models (e.g. gpt-4-1106-preview, gpt-4-vision-preview, dalle3, etc.) from OpenAI
  - talk directly with your text, pdf, and image files with by loading them directly in the current session context or by uploading them (currently only `.pdf` and `.txt` files are supported for vector db) into the VectorDB for long term storage and more extensive searching amongst personal out-of-ChatGPT training data.
  - example commands
  ```
  PA Commands:
  help             - show this message
  pa_llama         - toggle the use of a llama model to interpret an unknown command (huge WIP)
  remind me        - format is `[remind me], [description], [numerical value], [time unit (s,m,h)]`; sets a reminder that will ping you in a specified amount of time
  draw             - format is `[draw]; [prompt]` and it allows you to draw images using Dalle API from OpenAI, default is using Dalle3
  upload           - (vector db) upload a text document (.pdf or .txt) to be stored into the Vector DB
  query            - (vector db) query documents in the Vector DB to be used to talk with w/ ChatGPT; format is `[query] [prompt]`
  _attachTextFile  - Command only for GPT interpreter. Wrap any long code segments in <CODESTART> <CODEEND> and any commentary in <COMMENTSTART> <COMMENTEND>. DO NOT PUT EVERYTHING INTO A SINGLE LINE, use newlines, tabs, normal code formatting. format is `_attachTextFile [commentary] [code]` where each section can span multiple lines.

  GPT Commands:
  help              - display this message
  convo len         - show current gpt context length
  reset thread      - reset gpt context length
  show thread       - show the entire current convo context
  gptsettings       - show the current gpt settings
  gptset            - format is gptset, [setting_name], [new_value] modify gpt settings
  curr prompt       - get the current prompt name
  change prompt     - format is change prompt, [new prompt], change prompt to the specified prompt(NOTE: resets entire message thread)
  show prompts      - show the available prompts for gpt
  models            - list the available gpt models
  modify prompts    - modify the prompts for gpt
  save thread       - save the current gptX thread to a file
  show old threads  - show the old threads that have been saved
  load thread       - format is load thread, [unique id] load a gptX thread from a file
  delete thread     - format is delete thread, [unique id]` delete a gptX thread from a file
  current model     - show the current gpt model
  swap              - swap between different models
  ```
- Convenience access to a local stable diffusion server (uses automatic1111's `stable-diffusion-webui` repo)

## Quick setup (using pip/conda)
1. Prerequisites:
    - Get Discord Bot Token
      - New Application for Discord Bot on Discord Developer Portal
      - Invited your new bot into your discord server
        - Help: [video](https://www.youtube.com/watch?v=hoDLj0IzZMU) 
    - Get OpenAI API Key
      - You'll need to create an account with [OpenAI](https://openai.com/) and create an API key, put that in the `.env` file.
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
6. Run with `python ./main.py`; Optionally, you can run with debug mode `python ./main.py -d`
7. (Optional) Stable Diffusion
    > I use Automatic1111's `stable-diffusion-webui` repo, so `webui.sh` is the entrypoint that I run to start the stable diffusion server api server. It looks like their script clones the repo again inside of itself, which I find odd, but it will still work nonetheless and you'll need to place your model checkpoints inside the `models` folder in the nested cloned repo. The `webui.sh` script will automatically download a stable diffusion `v1.5-pruned-emaonly.safetensors` model weights file to get you started if you don't have your own weights.
    <br>
    I assume the submodule will just work. If it doesn't just clone the repo from here: [https://github.com/AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui)

## Future Plans
- add more commands for vector db to "converse with your personal docs"
  > NOTE: Remember that LLM's are prone to make things up and mix and match stuff and present it to you confidently as their truth, when in reality it could just be bs'ing you. Take caution with what you use this or any LLM-assisted application. You should always be weary of their hallucinations.
- make stable diffusion bot more user friendly (hah)
- add more commands to CommandInterpreter
- provide option to use local LLMs
  > NOTE: low priority since I and many people just don't have the hardware to run any actual decent LLM