from aiolimiter import AsyncLimiter
import httpx
import json
import re
from copy import deepcopy


class Translator:
    def __init__(self, conf):
        self.conf = conf
        self.limiter = AsyncLimiter(conf['qps'], 1)

    async def chat(self, url, body, headers):
        async with self.limiter:
            async with httpx.AsyncClient() as client:
                client_stream = client.stream("POST", url, headers=headers, json=body, timeout=360)
                async with client_stream as response:
                    async for line in response.aiter_lines():
                        if not line or line is None:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if line == "[DONE]":
                            break
                        data = json.loads(line)
                        if 'choices' in data and data['choices']:
                            contents = [c['delta']['content']
                                        for c in data['choices'] if 'delta' in c and 'content' in c['delta']]
                            yield ''.join(contents)

    async def translate(self, url, body, headers, to_english=True):
        messages = body['messages']
        if self.conf['save_dialog_num'] > 0 and len(messages) > self.conf['save_dialog_num']:
            messages = messages[-self.conf['save_dialog_num']:]
        messages[-1]['content'] += self.conf['prompt_to_en' if to_english else 'prompt_to_zh']
        body['messages'] = messages
        body['model'] = self.conf['model']
        body['temperature'] = self.conf['temperature']
        body['stream'] = True
        line = ''
        async for t in self.chat(url, body, headers):
            line += t
            if re.search(r'\[[0-9a-zA-Z]{0,10}$', line):  # 与 utils.generate_random_id 保持一致
                continue  # id 要整体返回
            yield line
            line = ''
        if line:
            yield line

    async def translate_wrap(self, url, body, headers, context=None):
        body = deepcopy(body)
        headers = deepcopy(headers)
        body['messages'] = deepcopy(context) if context else []
        async def translate(text, to_english=True):
            if 'messages' in body:
                body['messages'].append({'role': 'user', 'content': text})
            else:
                body['messages'] = [{'role': 'user', 'content': text}]
            async for line in self.translate(url, body, headers, to_english):
                yield line
        return translate
