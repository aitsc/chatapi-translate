import aiohttp
import asyncio
import hashlib
import random
import json
from urllib.parse import quote
from aiolimiter import AsyncLimiter


class Translator:
    def __init__(self, conf):
        self.conf = conf
        # self.semaphore = asyncio.Semaphore(conf['qps'])  # 协程并发限制
        self.limiter = AsyncLimiter(conf['qps'], 1)

    async def bdTrans_async(self, q, appid, secretKey, fromLang='auto', toLang='zh'):
        if isinstance(q, str):
            q = [q]
        dst_L = []
        numNone = 0
        myurl = '/api/trans/vip/translate'

        async with aiohttp.ClientSession() as session:
            for i, qi in enumerate(q):
                salt = random.randint(32768, 65536)
                sign = appid + qi + str(salt) + secretKey
                sign = hashlib.md5(sign.encode()).hexdigest()
                myurl = myurl + '?appid=' + appid + '&q=' + \
                    quote(qi) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign

                async with self.limiter:
                    try:
                        async with session.get(f'http://api.fanyi.baidu.com{myurl}') as response:
                            result_all = await response.text()
                            result = json.loads(result_all)
                    except Exception as e:
                        result = {'error_code': e}

                    if 'trans_result' in result:
                        dst_ = []
                        for j in result['trans_result']:
                            dst_.append(j['dst'])
                        dst = '\n'.join(dst_)
                    else:
                        print(result)
                        dst = None
                        numNone += 1
                    dst_L += [dst]
        return dst_L, numNone

    async def translate(self, text, to_english=True):
        if to_english:
            return (await self.bdTrans_async(text, self.conf['appid'], self.conf['secretKey'], toLang='en'))[0][0]
        else:
            return (await self.bdTrans_async(text, self.conf['appid'], self.conf['secretKey'], toLang='zh'))[0][0]


# Example usage
async def main():
    text = "你好"
    conf = {"appid": "your_appid", "secretKey": "your_secret_key", "qps": 1.}

    translator = Translator(conf)
    translated_text = await translator.translate(text)
    print(translated_text)


if __name__ == "__main__":
    asyncio.run(main())
