import random

def handle_response(msg) -> str:
    # lowercase 
    x = msg.lower()

    # single word-ish
    
    if x == "help":
        return "look at my source code, or if you need mental health, well, good luck"

    if x == "hi":
        return "hello"
    if x == "roll":
        return str(random.randint(1, 6))

    if x == "do you love me?":
        return "Of course not, idiot, you can't ask me such a thing..."

    if x == "pspsps":
        return "Meow"
    
    if x == "meow":
        return "*hiss*"

    if x[0:4] == 'calc':
        tmp = x.split(":")
        return eval(tmp[1])

    if x[0:10] == "reminder: ":
        return f"REMINDER: {x[10:]}"

    # multi word-ish
    y = x.split()

    if "you're" in y and "smart" in y:
        return "Thanks, master. <3"


    return "not sure what you said"