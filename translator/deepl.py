import aiohttp
import asyncio
from aiolimiter import AsyncLimiter


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
        if to_english:
            return await self.translate_text(text, 'EN', self.conf['api_key'])
        else:
            return await self.translate_text(text, 'ZH', self.conf['api_key'])


# Example usage
async def main():
    text = """测试:
def abc():
    treturn '你好'
结束"""
    conf = {"api_key": "your_api_key", "qps": 1.}
    translator = Translator(conf)

    translated_text = await translator.translate(text)
    print(translated_text)


if __name__ == "__main__":
    asyncio.run(main())
