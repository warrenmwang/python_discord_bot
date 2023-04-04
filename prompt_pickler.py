import pickle
'''
If you accidentally delete whatever prompts.txt file you have, and you need to repickle the prompt_name -> prompt dict, use this.
'''

SAVE=False

if SAVE:
    d = {}
    with open("./private/prompts.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            prompt_name = line.split("<SEP>")[0]
            prompt = line.split("<SEP>")[1]

            d[prompt_name] = prompt
        
    with open("./private/prompts.pkl", "wb") as f:
        pickle.dump(d, f, protocol=pickle.HIGHEST_PROTOCOL)
else:
    with open("./private/prompts.pkl", "rb") as f:
        d = pickle.load(f)

    for k, v in d.items():
        print(f"Name:{k}\nPrompt:{v}\n\n")

