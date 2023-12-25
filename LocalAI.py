import os
import discord
import requests
from PIL import Image
import io, base64
from Utils import run_bash, send_msg_to_usr, send_file_to_usr, constructHelpMsg, debug_log
import argparse
import time

class StableDiffusion:
    def __init__(self, debug:bool):
        self.DEBUG = debug
        self.tmp_dir = "./tmp"

        self.server_url = "http://127.0.0.1:7861"
        self.stable_diffusion_channel = os.getenv('STABLE_DIFFUSION_CHANNEL')
        self.stable_diffusion_output_dir = f"{self.tmp_dir}/stable_diffusion_output.png"
        self.stable_diffusion_toggle = False
        self.models = {
            '14': 'sd-v1-4.ckpt',
            '15': 'v1-5-pruned-emaonly.safetensors',
            '21': 'v2-1_768-ema-pruned.ckpt',
            'wd15': 'wd15-beta1-fp16.ckpt',
            'wd15-illusion': 'wd-illusion-fp16.safetensors',
            'wd15-ink': 'wd-ink-fp16.safetensors',
            'wd15-mofu': 'wd-mofu-fp16.safetensors',
            'wd15-radiance': 'wd-radiance-fp16.safetensors'
        }
        self.vaes = ['vae-ft-mse-840000-ema-pruned.ckp', 'kl-f8-anime2.ckpt'] # TODO: add option to switch to more vae's
        self.models_str = constructHelpMsg(self.models)
        self.available_model_names = list(self.models.keys()) 
        self.curr_model_name = '15'

        self.cmd_prefix = "!"
        self.help_dict = {
                "help": "show this message",
                "on": "start server and load default model to GPU",
                "off": "stop server and unload model from GPU",
                "status": "show status of server",
                "model": "show current model loaded/to be loaded",
                "swap [model_name]": "swaps currently loaded model (server needs to be on)",
                "models": "list available model checkpoints", # TODO: add cmd to list vaes
        }
        self.help_str = constructHelpMsg(self.help_dict)
        self.prompting_help = 'usage: `[prompt] -s [steps] -n [num] -h [height] -w [width] -c [cfg] -S [seed] -u [upscale value]`\nPrompt example: `photograph of a red, crispy apple, 4k, hyperdetailed -s 20 -n 4 -h 512 -w 512`'

        # parsing user input
        parser = argparse.ArgumentParser('Argument parser for user input for prompt and parameters.', add_help=False)
        parser.add_argument('prompt', help='Image generation prompt', nargs='*') # prompt must be first!
        parser.add_argument('-s', '--step', type=int, 
                            help='Number of steps to iterate (each step computes the delta from current pixels to pixels "closer" to prompt)', 
                            required=False,
                            default=20)
        parser.add_argument('-n', '--num', type=int, help='Number of images to create', 
                            required=False,
                            default=1)
        parser.add_argument('-h', '--height', type=int, help='Height in pixels', 
                            required=False,
                            default=768)
        parser.add_argument('-w', '--width', type=int, help='Width in pixels', 
                            required=False,
                            default=768)
        parser.add_argument('-c', '--cfg', type=float, help='CFG scale (higher means follow prompt more)', 
                            required=False,
                            default=8.5)
        parser.add_argument('-S', '--seed', type=int,
                            help="Seed (controls randomness)",
                            required=False,
                            default=-1)
        parser.add_argument('-u', '--upscale', type=float,
                            help="Resolution upscale value (e.g. 1.5 or 2) -- an input value will enable the upscaler",
                            required=False,
                            default=None)

        # TODO: add negatie prompt optional arg

        self.parser = parser

        # stop any existing servers at start
        self.stop_server()

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
                self.stop_server() 
                await send_msg_to_usr(msg, "SD OFF.")

            elif usr_msg == 'on' and self.stable_diffusion_toggle == True:
                await send_msg_to_usr(msg, 'Already on.')

            elif usr_msg == 'on' and self.stable_diffusion_toggle == False:
                await send_msg_to_usr(msg, 'Turning on SD (waiting for response)...')
                self.start_server() 
                await send_msg_to_usr(msg, "SD server on.")
            
            elif usr_msg == 'model':
                await send_msg_to_usr(msg, self.curr_model_name)
            
            elif usr_msg[:4] == 'swap':
                if len(usr_msg.strip()) > 4:
                    model_name = usr_msg.split()[1]
                    model_name = usr_msg[5:]
                    await self.swap_models(msg, model_name)
                else:
                    await send_msg_to_usr(msg, "Usage: swap [model_name]")
            
            elif usr_msg == 'models':
                await send_msg_to_usr(msg, self.models_str)

            elif usr_msg == 'help':
                help_str = f"Commands:\n{self.help_str}\nPrompting Help:\n{self.prompting_help}"
                await send_msg_to_usr(msg, help_str)

            else:
                await send_msg_to_usr(msg, 'use !help for help')

            return

        # input is a txt2img prompt
        if self.stable_diffusion_toggle: 
            await self.sd_txt2img(msg, usr_msg) 
        else:
            await send_msg_to_usr(msg, "Stable Diffusion is not loaded. Load it by running !on (be sure you have enough VRAM).")

    
    async def sd_txt2img(self, msg : discord.message.Message, usr_msg : str) -> None:
        '''
        Generate an image via POST request to localhost stablediffusion api server.
        '''
        # argparse the input string for options like step size, number of imgs, etc.
        try:
            args = self.parser.parse_args(usr_msg.split())
        except Exception as e:
            await send_msg_to_usr(msg, "Parsing error -- check your input.")
            return

        prompt = ' '.join(args.prompt)
        step = args.step
        num = args.num
        height = args.height
        width = args.width
        cfg = args.cfg
        seed = args.seed
        upscale = args.upscale
        if upscale is None:
            enable_upscale = False
        else:
            enable_upscale = True
        upscaler = "ESRGAN_4x" # possible (don't actually know if i have all of these) - Lanczos, Nearest, LDSR, ESRGAN_4x, ScuNET GAN, ScuNET PSNR, SwinIR 4x

        # these can be adjustable, tho need to figure out what they mean
        payload = {
                    "prompt": prompt,
                    "enable_hr": enable_upscale,
                    "denoising_strength": 0,
                    "firstphase_width": 0,
                    "firstphase_height": 0,
                    "hr_scale": upscale,
                    "hr_upscaler": upscaler,
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
                    "seed": seed,
                    # "subseed": -1,
                    # "subseed_strength": 0,
                    # "seed_resize_from_h": -1,
                    # "seed_resize_from_w": -1,
                    # "sampler_name": "Euler",
                    # "batch_size": 1,
                    "n_iter": num,
                    "steps": step,
                    "cfg_scale": cfg,
                    "width": width,
                    "height": height,
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

        if self.DEBUG: debug_log(f'{prompt=}\n{step=}\n{num=}\n{height=}\n{width=}\n{cfg=}\n{seed=}\n{upscale=}\n{payload=}')

        await send_msg_to_usr(msg, f"Creating image with input: `{usr_msg}`")

        response = requests.post(url=f'{self.server_url}/sdapi/v1/txt2img', json=payload)
        r = response.json()

        if self.DEBUG: debug_log(f'{r=}')

        for i in r['images']:
            image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))
            image.save(self.stable_diffusion_output_dir)
            await send_file_to_usr(msg, self.stable_diffusion_output_dir)

    def start_server(self):
        '''
        load the model onto the gpu with the REST API params
        '''
        cmd = 'tmux new-session -d -s sd_api && tmux send-keys -t sd_api "cd stable-diffusion-webui && ./webui.sh --xformers --disable-safe-unpickl --nowebui" C-m'
        run_bash(cmd)
        if self.DEBUG: debug_log("Starting sd server...")
        time.sleep(10) # LOL...
        if self.DEBUG: debug_log("Server started.")
        self.stable_diffusion_toggle = True

        if self.DEBUG: debug_log("Loading default model...")
        self._swap_models(self.curr_model_name)
        if self.DEBUG: debug_log("Loaded default model.")

    def stop_server(self):
        '''
        unload the model
        '''
        cmd = 'tmux kill-session -t sd_api'
        run_bash(cmd)
        if self.DEBUG: debug_log("Stopped sd current server.")
        self.stable_diffusion_toggle = False
    
    def _swap_models(self, model_name : str) -> None:
        '''swaps model helper function (requires model to be loaded) (core functionality) -- without async'''
        # unload current model
        response = requests.post(url=f"{self.server_url}/sdapi/v1/unload-checkpoint")
        if self.DEBUG: debug_log(f'unload checkpoint - {response=}')

        # change model checkpoint to use
        option_payload = {
            "sd_model_checkpoint": self.models[model_name],
            "sd_vae": self.vaes[1] if "wd15" in model_name else self.vaes[0] # swap vae for waifu diffusion models.
        }
        response = requests.post(url=f'{self.server_url}/sdapi/v1/options', json=option_payload)
        if self.DEBUG: debug_log(f'options checkpoint - {response=}')

        # reload current model
        response = requests.post(url=f"{self.server_url}/sdapi/v1/reload-checkpoint")
        if self.DEBUG: debug_log(f'reload checkpoint - {response=}')

        # update curr model tracker
        self.curr_model_name = model_name
    
    async def swap_models(self, msg : discord.message.Message, model_name : str) -> None:
        '''
        swap model loaded (requires model to be loaded)
        '''
        # check server is on
        if not self.stable_diffusion_toggle:
            await send_msg_to_usr(msg, "Need to start server.")
            return
        
        # check model_name is valid
        if model_name not in self.available_model_names:
            await send_msg_to_usr(msg, f"Model not found.\nAvailable models:\n{self.available_model_names}")
            return
        
        # swap
        self._swap_models(model_name)

        await send_msg_to_usr(msg, f"Model swapped to {model_name}")


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
