import aiohttp
import asyncio
import json
from aiolimiter import AsyncLimiter
import html


class Translator:
    def __init__(self, conf):
        self.conf = conf
        self.limiter = AsyncLimiter(conf['qps'], 1)

    async def google_translate_async(self, q, api_key, target_lang='zh'):
        if isinstance(q, str):
            q = [q]
        translations = []
        num_none = 0
        url = f'https://translation.googleapis.com/language/translate/v2?key={api_key}'

        async with aiohttp.ClientSession() as session:
            for i, qi in enumerate(q):
                payload = {
                    'q': [qi],
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
                        translations_ = []
                        for j in result['data']['translations']:
                            translations_.append(html.unescape(j['translatedText']))
                        translation = '\n'.join(translations_)
                    else:
                        print(result)
                        translation = None
                        num_none += 1
                    translations += [translation]
        return translations, num_none

    async def translate(self, text, to_english=True):
        text = text.split('\n')
        if to_english:
            ret = (await self.google_translate_async(text, self.conf['api_key'], target_lang='en'))[0]
        else:
            ret = (await self.google_translate_async(text, self.conf['api_key'], target_lang='zh-CN'))[0]
        return '\n'.join(ret)


# Example usage
async def main():
    text = """测试:
def abc():
    return '你好'
结束"""
    conf = {"api_key": "your_api_key", "qps": 1.}

    translator = Translator(conf)
    translated_text = await translator.translate(text)
    print(translated_text)


if __name__ == "__main__":
    asyncio.run(main())
