import aiohttp
import json
from aiolimiter import AsyncLimiter
import html
from .utils import iter_lines


class Translator:
    def __init__(self, conf):
        self.conf = conf
        self.limiter = AsyncLimiter(conf['qps'], 1)

    async def google_translate_async(self, q, api_key, target_lang='zh'):
        if isinstance(q, str):
            q = q.split('\n')
        num_none = 0
        url = f'https://translation.googleapis.com/language/translate/v2?key={api_key}'

        async with aiohttp.ClientSession() as session:
            payload = {
                'q': q,
                'target': target_lang,
            }

            async with self.limiter:
                try:
                    async with session.post(url, json=payload) as response:
                        result_all = await response.text()
                        result = json.loads(result_all)
                except Exception as e:
                    result = {'error': e}

                if 'data' in result:
                    translation = []
                    for j in result['data']['translations']:
                        translation.append(html.unescape(j['translatedText']))
                else:
                    print(result)
                    translation = []
                    num_none += 1
        return translation, num_none

    async def translate(self, text, to_english=True):
        for t, t_restore in iter_lines(text, buffer=self.conf['buffer'], leave_blank=False):
            if to_english:
                ret = (await self.google_translate_async(t, self.conf['api_key'], target_lang='en'))[0]
            else:
                ret = (await self.google_translate_async(t, self.conf['api_key'], target_lang='zh-CN'))[0]
            t = '\n'.join(ret)
            yield t_restore(t)
