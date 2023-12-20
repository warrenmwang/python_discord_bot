import os
import discord
import requests
from PIL import Image
import io, base64
from Utils import run_bash, send_msg_to_usr, send_file_to_usr, constructHelpMsg

class StableDiffusion:
    def __init__(self, debug:bool):
        self.DEBUG = debug
        self.tmp_dir = "./tmp"
        self.stable_diffusion_channel = os.getenv('STABLE_DIFFUSION_CHANNEL')
        self.stable_diffusion_output_dir = f"{self.tmp_dir}/stable_diffusion_output.png"
        self.stable_diffusion_toggle = False
        self.cmd_prefix = "!"
        self.help_dict = {
                "help": "show this message",
                "on": "load model to GPU",
                "off": "unload model from GPU",
                "status": "display if model is loaded or not"
        }
        self.help_str = constructHelpMsg(self.help_dict)

    async def main(self, msg : discord.message.Message) -> None:
        '''
        Entrance function into doing anything with stable diffusion.
        '''
        usr_msg = str(msg.content)
        # cmd (help, status, on, off)
        if usr_msg[0] == self.cmd_prefix:
            usr_msg = usr_msg[1:].lower()
            if usr_msg == 'status':
                await send_msg_to_usr(msg, 'ON' if self.stable_diffusion_toggle else 'OFF')
            elif usr_msg == 'off' and self.stable_diffusion_toggle == False:
                await send_msg_to_usr(msg, 'Already off.')
            elif usr_msg == 'off' and self.stable_diffusion_toggle == True:
                await self.sd_unload_model() 
                await send_msg_to_usr(msg, "SD OFF.")
                self.stable_diffusion_toggle = False
            elif usr_msg == 'on' and self.stable_diffusion_toggle == True:
                await send_msg_to_usr(msg, 'Already on.')
            elif usr_msg == 'on' and self.stable_diffusion_toggle == False:
                await self.sd_load_model() 
                await send_msg_to_usr(msg, 'Turning on SD (wait like 5 seconds for it to load)...')
                self.stable_diffusion_toggle = True
            elif usr_msg == 'help':
                await send_msg_to_usr(msg, self.help_str)
            else:
                await send_msg_to_usr(msg, 'use !help for help')
            return

        # input is a txt2img prompt
        if self.stable_diffusion_toggle: # note api is NOT loaded by default -- load/reload and unload manually
            await self.sd_txt2img(msg, usr_msg) # TODO: copy the input parameters formatting that midjourney uses
        else:
            await send_msg_to_usr(msg, "Stable Diffusion is not loaded. Load it by running !on (be sure you have enough VRAM).")

    
    async def sd_txt2img(self, msg : discord.message.Message, usr_msg : str) -> None:
        '''
        ping the localhost stablediffusion api 
        '''
        # these can be adjustable, tho need to figure out what they mean
        payload = {
                    "prompt": usr_msg,
                    # "enable_hr": False,
                    # "denoising_strength": 0,
                    # "firstphase_width": 0,
                    # "firstphase_height": 0,
                    # "hr_scale": 2,
                    # "hr_upscaler": "string",
                    # "hr_second_pass_steps": 0,
                    # "hr_resize_x": 0,
                    # "hr_resize_y": 0,
                    # "hr_sampler_name": "string",
                    # "hr_prompt": "",
                    # "hr_negative_prompt": "",
                    # "prompt": "",
                    # "styles": [
                    #     "string"
                    # ],
                    # "seed": -1,
                    # "subseed": -1,
                    # "subseed_strength": 0,
                    # "seed_resize_from_h": -1,
                    # "seed_resize_from_w": -1,
                    # "sampler_name": "Euler",
                    # "batch_size": 1,
                    "n_iter": 1,
                    "steps": 25,
                    "cfg_scale": 8.5,
                    "width": 768,
                    "height": 768,
                    # "restore_faces": False,
                    # "tiling": False,
                    # "do_not_save_samples": False,
                    # "do_not_save_grid": False,
                    # "negative_prompt": "string",
                    # "eta": 0,
                    # "s_min_uncond": 0,
                    # "s_churn": 0,
                    # "s_tmax": 0,
                    # "s_tmin": 0,
                    # "s_noise": 1,
                    # "override_settings": {},
                    # "override_settings_restore_afterwards": True,
                    # "script_args": [],
                    # "sampler_index": "Euler",
                    # "script_name": "string",
                    # "send_images": True,
                    # "save_images": False,
                    # "alwayson_scripts": {}
                }

        await send_msg_to_usr(msg, f"Creating image of \"{usr_msg}\"")

        response = requests.post(url=f'http://127.0.0.1:7860/sdapi/v1/txt2img', json=payload)
        r = response.json()
        # DEBUG
        # print(r.keys())
        # for k in r.keys():
        #     print(f'{r[k]=}')

        # TODO: use PIL to manually make a grid of the 4 images into a single image to be return to the user.
        for i in r['images']:
            image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
            image.save(self.stable_diffusion_output_dir)
            await send_file_to_usr(msg, self.stable_diffusion_output_dir)

    async def sd_load_model(self):
        '''
        load the model onto the gpu with the REST API params
        '''
        cmd = 'tmux new-session -d -s sd_api && tmux send-keys -t sd_api "cd stable-diffusion-webui && ./webui.sh --xformers --disable-safe-unpickl --api" C-m'
        run_bash(cmd)

    async def sd_unload_model(self):
        '''
        unload the model
        '''
        cmd = 'tmux kill-session -t sd_api'
        run_bash(cmd)

class LLM:
    '''
    General class for any kind of local large language model (LLAMA, LLAMA2, LLAMA variants)
    or small language models / GPT models
    '''
    def __init__(self, arch : str, model : str, prompt : str, maxGenLen : int = 100) -> None:
        '''
        arch - type of model (llama, nanogpt)
        model - currently used to distinguish which kind of LLAMA model to use 
        maxGenLen - maximum length of text generations desired 
        '''
        self.arch = arch # e.g. llama
        self.model = model # e.g. 7B, 13B
        self.maxGenLen = maxGenLen # maximum length of text generation
        self.prompt = prompt # prompt for generations

    async def generate(self, usr_str : str) -> str:
        '''
        Generates a text output based on the usr_str with the arch/model specified
        '''
        # if self.arch == "nanogptShakespeare":
        #     return await self.runNanoShakespeare(self.maxGenLen)
        # elif self.arch == "llama":
        #     return await self.runLLAMA(usr_str)

        return await self.runLLAMA(usr_str)

    async def runLLAMA(self, usr_str:str)->str:
        '''
        given the user str help the user figure out what they want to do by using a local llama program to figure it out
        no chatgpt here...(this is pretty bad tho if im only using 7B)
        '''
        input_ = f"{self.prompt}\n\nUser: {usr_str}\nAgent:"
        cmd = f'cd llama.cpp && ./main -m ./models/{self.model}/ggml-model-q4_0.gguf -n 128 -p "{input_}" -e'
        stdout, _ = run_bash(cmd)
        ret = stdout.split("Agent:")[1]
        return ret
        
    # async def runNanoShakespeare(self, length : int)->str:
    #     '''
    #     generates a random shakespeare snippet from a local GPT trained on shakespeare
    #     from nanoGPT repo

    #     cut the generation output to be of the input length 

    #     this is duct-taped together im sorry
    #     '''
    #     stdout, stderr = run_bash(f'cd nanoGPT && /home/wang/anaconda3/envs/dev2-py310/bin/python sample.py --out_dir=../ml_weights/shakespeare --max_new_tokens={length}')
    #     if len(stderr) != 0:
    #         return f"generation failed -> {stderr}"
    #     else:
    #         stdout = stdout.split("\n\n")
    #         return '\n\n'.join(stdout[1:])
