import random
import os
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
    "you’re so smart":"thanks master :) <3"
}

def handle_response(msg) -> str:
    # lowercase 
    x = msg.lower()

    if x[0:5] == "echo:":
        tmp = x[5:]
        return tmp

    try:
        return d[x]
    except Exception as e:
        pass

    if x == "diceroll":
        return str(random.randint(1, 6))

    # slightly danger zone where I'm running code...
    if x[0:5] == 'calc:':
        tmp = x.split(":")
        return eval(tmp[1])
    if x[0:5] == 'exec:':
        tmp = x.split(":")
        os.system(tmp[1])
        return f"{tmp[1]} executed"

    if x[0:10] == "reminder: ":
        return f"REMINDER: {x[10:]}"

    return "not sure what you said"