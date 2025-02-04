'''
Test that the command line prefix commands work in their respective settings
and classes.
'''
import unittest
import sys
sys.path.append('..')
from GenerativeAI import LLM_Controller
from Utils import Message
from CommandInterpreter import CommandInterpreter
from PersonalAssistant import PersonalAssistant
import io

from dotenv import load_dotenv
load_dotenv()

class TestChatGPT(unittest.IsolatedAsyncioTestCase):
    '''Test the ChatGPT classes' hard coded command features.'''
    @classmethod
    def setUpClass(cls) -> None:
        cls.message = Message(msgType='test')
        cls.chatgpt: LLM_Controller = LLM_Controller()

    async def test_help(self):
        '''test can get help message'''
        self.message.content = '!help'
        self.assertTrue('help' in await self.chatgpt.main(self.message))

    async def test_change_model(self):
        '''test get change model'''
        self.message.content = '!cm'
        initModel = await self.chatgpt.main(self.message)
        self.message.content = '!gptset model gpt-4'
        await self.chatgpt.main(self.message)
        self.message.content = '!cm'
        secondModel = await self.chatgpt.main(self.message)
        self.assertNotEqual(initModel, secondModel)
        self.assertTrue('gpt-4' in secondModel)
        # check gpt-4 specific model params
        self.message.content = '!gptsettings'
        gptparams = (await self.chatgpt.main(self.message)).split('\n')
        maxTokens = int(gptparams[6].split('=')[1].strip())
        self.assertEqual(maxTokens, 8192)
        knowledgeCutoff = gptparams[8].split('=')[1].strip()
        self.assertEqual(knowledgeCutoff, 'Sep 2021')
        # change to vision preview model and check params
        self.message.content = '!gptset model gpt-4-vision-preview'
        gptparams = (await self.chatgpt.main(self.message)).split('\n')
        maxTokens = int(gptparams[6].split('=')[1].strip())
        self.assertEqual(maxTokens, 4096)
        knowledgeCutoff = gptparams[8].split('=')[1].strip()
        self.assertEqual(knowledgeCutoff, 'Apr 2023')
        # change to gpt-4-0125-preview and check params
        self.message.content = '!gptset model gpt-4-0125-preview'
        gptparams = (await self.chatgpt.main(self.message)).split('\n')
        maxTokens = int(gptparams[6].split('=')[1].strip())
        self.assertEqual(maxTokens, 4096)
        knowledgeCutoff = gptparams[8].split('=')[1].strip()
        self.assertEqual(knowledgeCutoff, 'Dec 2023')

    async def test_swap(self):
        '''test swapping models'''
        self.message.content = '!cm'
        firstModel = await self.chatgpt.main(self.message)
        self.message.content = '!swap'
        secondModel = await self.chatgpt.main(self.message)
        self.assertNotEqual(firstModel, secondModel)
    
    async def test_get_convo_len(self):
        '''test getting current thread length '''
        # get initial length
        self.message.content = '!cl'
        firstLength = await self.chatgpt.main(self.message)
        firstLength = int(firstLength.split(" ")[0].split(":")[1])
        # add a message
        self.message.content = "!_add_msg_to_curr_thread<SEP>user<SEP>hello world"
        await self.chatgpt.main(self.message)
        # get new length
        self.message.content = '!cl'
        secondLength = await self.chatgpt.main(self.message)
        secondLength = int(secondLength.split(" ")[0].split(":")[1])
        # ensure new length is longer than first length
        self.assertTrue(secondLength > firstLength)
        # clear thread and then check that length matches the firstLength
        self.message.content = '!rt'
        await self.chatgpt.main(self.message)
        self.message.content = '!cl'
        thirdLength = await self.chatgpt.main(self.message)
        thirdLength = int(thirdLength.split(" ")[0].split(":")[1])
        self.assertTrue(firstLength == thirdLength)
        
    async def test_show_thread(self):
        '''test show thread command'''
        self.message.content = '!st'
        ret = await self.chatgpt.main(self.message)
        self.assertTrue(len(ret) > 0) # system role (assumed non-zero length str should be in context)

        # add a message to thread
        role = 'system'.capitalize()
        content = 'hello human, what do u want?'
        self.message.content = f"!_add_msg_to_curr_thread<SEP>{role}<SEP>{content}"
        await self.chatgpt.main(self.message)
        self.message.content = '!st'
        ret = await self.chatgpt.main(self.message)
        self.assertTrue(role in ret)
        self.assertTrue(content in ret)

class TestCommandInterpreter(unittest.IsolatedAsyncioTestCase):
    '''Test functionality of commands hard coded into the CommandInterpreter.'''
    @classmethod
    def setUpClass(cls) -> None:
        cls.message = Message(msgType='test')
        cls.cmdInterp = CommandInterpreter(help_str='help str')

    async def test_remind_me(self):
        '''test the remind me feature.'''
        # Capture stdout to check reminder message
        captured_output = io.StringIO()
        sys.stdout = captured_output

        self.message.content = 'remind me, call grandma, 0.01, s'
        await self.cmdInterp.main(self.message) # this is awaited, so reminder will finish

        sys.stdout = sys.__stdout__ # reset stdout for other tests

        output = captured_output.getvalue()
        self.assertIn("Reminder set for 'call grandma' in 0.01 s", output)
        self.assertIn("REMINDER: call grandma", output)

    # TODO:

class TestPersonalAssistant(unittest.IsolatedAsyncioTestCase):
    ''''''
    @classmethod
    def setUpClass(cls) -> None:
        cls.message = Message(msgType='test')
        cls.pa = PersonalAssistant()

    # TODO:

if __name__ == '__main__':
    unittest.main()
