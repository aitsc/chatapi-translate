import aiohttp
from aiolimiter import AsyncLimiter
from .utils import iter_lines


class Translator:
    def __init__(self, conf):
        self.conf = conf
        self.limiter = AsyncLimiter(conf['qps'], 1)

    async def translate_text(self, text, target_language, api_key):
        url = "https://api-free.deepl.com/v2/translate"
        headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
        data = {
            "text": text,
            "target_lang": target_language,
        }

        async with aiohttp.ClientSession() as session:
            async with self.limiter:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status != 200:
                        raise Exception(f"DeepL API request failed with status code {response.status}: {await response.text()}")

                    response_json = await response.json()
                    translated_text = response_json["translations"][0]["text"]
                    return translated_text

    async def translate(self, text, to_english=True):
        for t, t_restore in iter_lines(text, buffer=self.conf['buffer'], leave_blank=True):
            if to_english:
                t = await self.translate_text(t, 'EN', self.conf['api_key'])
            else:
                t = await self.translate_text(t, 'ZH', self.conf['api_key'])
            yield t_restore(t)
