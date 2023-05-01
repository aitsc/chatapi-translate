import aiohttp
import hashlib
import random
import json
from urllib.parse import quote
from aiolimiter import AsyncLimiter
from .utils import iter_lines


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
        for t, t_restore in iter_lines(text, buffer=self.conf['buffer'], leave_blank=False):
            if to_english:
                t = (await self.bdTrans_async(t, self.conf['appid'], self.conf['secretKey'], toLang='en'))[0][0]
            else:
                t = (await self.bdTrans_async(t, self.conf['appid'], self.conf['secretKey'], toLang='zh'))[0][0]
            yield t_restore(t)
