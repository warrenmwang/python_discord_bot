# AI-Powered Discord ChatBot
Honestly I'm just trying to see what it's like to make a discord bot with an amalgamation of random functionalities and seeing if it's useful. "One bot to rule them all" kind of feel.

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
- Convenience access to a local stable diffusion server (use automatic1111 with `--api` flag)

## Quick setup (using pip/conda)
1. Prerequisites:
 - Discord Account
 - New Application for Discord Bot on Discord Developer Portal
 - Invited your new bot into your discord server
   - Help: [video](https://www.youtube.com/watch?v=hoDLj0IzZMU) 
2. Clone/fork this repo
3. `cd` into the repo
4. `pip install -r requirements`
6. Create a `.env` file and put all your information in there
7. `python ./main.py`
8. Start talking!
9. Well, you'll need other stuff if you want to run the ml stuff, you can figure that out :)

## Other Dependencies...
- StableDiffusion (yes it's integrated, but it's really hacky, uses old automatic1111 api server and makes http requests to local server for prompting and generating/retrieving images)
  - > haven't fixed the submodules dependency, so don't plan on stable diffusion working rn

## Future Plans
- add more commands for vector db