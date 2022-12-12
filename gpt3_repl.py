import openai
import os
from dotenv import load_dotenv
import subprocess

load_dotenv()

NUM_TRIES = 5

ORIGINAL_GPT3_REPL_PROMPT_FILENAME = os.getenv("ORIGINAL_GPT3_REPL_PROMPT_FILENAME")
GPT3_REPL_WORKING_PROMPT_FILENAME = os.getenv("GPT3_REPL_WORKING_PROMPT_FILENAME")
GPT3_REPL_PYTHON_BIN = os.getenv("GPT3_REPL_PYTHON_BIN")
GPT3_REPL_SCRIPT_FILENAME = os.getenv("GPT3_REPL_SCRIPT_FILENAME")
GPT3_REPL_OUTTEXT_FILENAME = os.getenv("GPT3_REPL_OUTTEXT_FILENAME")
GPT3_REPL_ERRTEXT_FILENAME = os.getenv("GPT3_REPL_ERRTEXT_FILENAME")

# settings for writing python script
GPT3_REPL_SETTINGS = { 
    "engine": ["code-davinci-002","str"],
    "temperature": ["0.0","float"],
    "max_tokens": ["500","int"],
    "top_p": ["1.0","float"],
    "frequency_penalty": ["0.0", "float"],
    "presence_penalty": ["0.0", "float"],
    "stop": [["Question:", "Out:", "Err:" ,"STOP"], 'list of str']
}


def gen_gpt3_repl_ver(usr_msg : str, settings_dict: dict = GPT3_REPL_SETTINGS) -> str:
    '''
    retrieves a GPT3 response given a string input and a dictionary containing the settings to use
    returns the response str
    '''
    response = openai.Completion.create(
        engine = settings_dict["engine"][0],
        prompt = usr_msg,
        temperature = float(settings_dict["temperature"][0]),
        max_tokens = int(settings_dict["max_tokens"][0]),
        top_p = float(settings_dict["top_p"][0]),
        frequency_penalty = float(settings_dict["frequency_penalty"][0]),
        presence_penalty = float(settings_dict["presence_penalty"][0]),
        stop = settings_dict["stop"][0]
    )
    return response.choices[0].text

def gen_gpt3_from_prompt():
    '''
    generate python code from the current working prompt file
    write the generated code to a file and ask if user wants to run it or not

    return 1 if don't need to run python code, answer is generated already
    return 0 if we have generated code
    '''

    # read the prompt barebones
    with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "r+") as f:
        prompt = f.read()
        response = gen_gpt3_repl_ver(prompt)
        f.write(response) 

    # check to see if we need to run python code...
    lines, status = check_if_need_run_python_code()
    if not status:
        return 1

    # need to run python code, get the python script
    lines = lines[:-1] # ignore the last ```
    python_script = []
    for i in range(len(lines)-1, 0, -1):
        if(lines[i].strip("\n") != "```"):
            line = lines[i]
            python_script.insert(0, line)
        else:
            break
    full_python_script = "".join(python_script)

    # run the code and append the output to the file with no newline
    with open(GPT3_REPL_SCRIPT_FILENAME, "w") as f:
        f.write(full_python_script)
    return 0


def run_generated_code():
    '''
    runs the generated python code, saves output and error
    '''

    # run the code in the dedicated file to store generated scripts
    cmd = f"{GPT3_REPL_PYTHON_BIN} {GPT3_REPL_SCRIPT_FILENAME} 1> {GPT3_REPL_OUTTEXT_FILENAME} 2> {GPT3_REPL_ERRTEXT_FILENAME}"
    try:
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print(f"Got the following error trying to run subprocess: {e}")
        return -1
    return 0

def check_if_need_run_python_code():
    '''
    used by gen_gpt3_from_prompt()
    returns True if we have a script to run
    else return False
    '''
    # check to see if we need to run python code...
    lines = []
    with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "r+") as f:
        lines = f.readlines()

        # ignore final blank line if exists
        if lines[-1] == "":
            lines = lines[:-1]

        if lines[-1].strip("\n") != "```":
            # don't need to run python code, just return
            return [], False

    return lines, True

def check_error():
    '''
    returns True if there was an error, False otherwise
    '''
    err_flag = False
    with open(GPT3_REPL_ERRTEXT_FILENAME, "r") as f:
        f_contents = f.read()
        if(f_contents == ""):
            # no err
            pass
        else:
            # yes err, write this to the output file...
            err_flag = True

    return err_flag

def cleanup():
    '''
    deletes all files in the tmp directory for this project
    '''
    for file in os.listdir("./tmp/"):
        file_path = os.path.join("./tmp/", file)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            return


'''
new function step one
'''
def answer_one_question_step_one(usr_msg : str):
    '''
    given the usr_msg, try to generate the answer directly first, if not will generate python code
    '''
    
    # copy the contents of the original prompt file into a working prompt file
    with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "w") as f:
        with open(ORIGINAL_GPT3_REPL_PROMPT_FILENAME, "r") as f2:
            f.write(f2.read())

    # write the user's message to the prompt file
    with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "a") as f:
        f.write(usr_msg)

    # generate the gpt3 response
    rc = gen_gpt3_from_prompt()
    # rc == 1 if direct answer
    # rc == 0 if have generated python code
    if(rc == 1): # direct answer
        return 1
    else:
        return 0 

'''
currently only allows a single try for the code generated, maybe in the future we will allow multiple tries like in the original
implementation i tried
'''
def answer_one_question_step_two(usr_msg: str):
    '''
    usr_msg is either [y/n]
    so run the python code and return the answer if given y
    else abort if given n

    cleanup
    '''
    if(usr_msg.lower() == 'y'):
        rc = run_generated_code()
        if rc == -1:
            cleanup()
            return "error occurred"
        else:
            # success
            with open(GPT3_REPL_OUTTEXT_FILENAME, "r") as f:
                tmp = f.readlines()
                answer = tmp[-1] # get answer (expect one line answers for now)
                cleanup()
                return answer
    else:
        # abortting
        cleanup()
        return "Aborting."




'''

older function, leaving it here for reference

'''
# def answer_one_question(usr_msg : str):
#     '''
#     return 0 for good generation
#     return 1 for bad generation
#     '''

#     # copy the contents of the original prompt file into a working prompt file
#     with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "w") as f:
#         with open(ORIGINAL_GPT3_REPL_PROMPT_FILENAME, "r") as f2:
#             f.write(f2.read())

#     # write the user's message to the prompt file
#     with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "a") as f:
#         f.write(usr_msg)

#     # generate the gpt3 response
#     rc = gen_gpt3_from_prompt()
#     if(rc == 1):
#         return 0
#     elif(rc == -1):
#         cleanup()
#         return 1

#     # check for an error
#     if not check_error():
#         # read the output from out.txt, write it back to the prompt file
#         ans = ""
#         with open(GPT3_REPL_OUTTEXT_FILENAME, "r") as f:
#             ans = f.read()

#         with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "a") as f:
#             f.write(f"Out: {ans}")

#         # generate the gpt3 response
#         rc = gen_gpt3_from_prompt()
#         if(rc == 1):
#             cleanup()
#             return 0
#         elif(rc == -1):
#             cleanup()
#             return 1
#         cleanup()
#         return 0
#     else:
#         # we had an error....
#         for _ in range(NUM_TRIES):
#             # every time we error out, increase the temperature...it needs
#             # more creativity to solve this problem xD
#             GPT3_SETTINGS["temperature"] += 0.20
#             print(f"Try {_}")

#             # read the error from err.txt, write it back to the prompt file
#             err = ""
#             with open(GPT3_REPL_ERRTEXT_FILENAME, "r") as f:
#                 err = f.read()

#             with open(GPT3_REPL_WORKING_PROMPT_FILENAME, "a") as f:
#                 f.write(f"Err: {err}")

#             # generate the gpt3 response
#             rc = gen_gpt3_from_prompt()
#             if(rc == 1):
#                 cleanup()
#                 return 0
#             elif(rc == -1):
#                 cleanup()
#                 return 1

#             # check if had error, if so, repeat loop
#             if not check_error():
#                 # cleanup and leave
#                 cleanup()
#                 return 0
#         print("OUT OF TRIES!!!")
#         cleanup()
#         return 1

