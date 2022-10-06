import os
import discord
from dotenv import load_dotenv
load_dotenv()

MY_NAME = os.getenv('MY_NAME')

d = {
    "hi":"Hello my precious human! __meow__ :)",
    "hello":"Hello my precious human! __meow__ :)",
    "goodnight":"Goodnight! <3",
    "good night":"Goodnight! <3",
    "goodmorning":"Good morning! <3",
    "good morning":"Good morning! <3",
    "good afternoon":"Good afternoon! <3",
    "i love you!":f"I love you too, {MY_NAME}! uwu <3",
    "i love you":f"I love you too, {MY_NAME}! uwu <3",
    "ily!":"ily more",
    "ily":"ily more",
    "uwu":"UWUWUWUWWUWW",
    ";-;":"what's wrong?",
    "sadge":"don't be sad :/",
    "*pets*":"*smiles*",
    "pspsps":"**hiss**",
    "meow":'*Meow*',
    "help":"look at my source code, or if you need mental health, well, good luck",
    "do you love me?":"Of course not, idiot, you can't ask me such a thing...",
    "you're cute":"me? *looks at your adoringly*",
    "you’re cute":"me? *looks at your adoringly*",
    "you're so smart":"thanks master :) <3",
    "you’re so smart":"thanks master :) <3",
    "how are you?":"I'm doing great, now that you're here ;)"
}

# these are mostly random functionalities
def handle_response(msg : discord.message.Message) -> str:
    try:
        return d[msg.lower()]
    except Exception as e:
        pass

    if "aww" in msg:
        return "😊"

    return "not sure what you said"