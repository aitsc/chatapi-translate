import aiohttp
import json
import hmac
import hashlib
import base64
from aiolimiter import AsyncLimiter
import uuid
import datetime
from .utils import iter_lines


class Translator:
    def __init__(self, conf):
        self.conf = conf
        self.limiter = AsyncLimiter(conf['qps'], 1)

    @staticmethod
    def md5_base64(s):
        md5 = hashlib.md5(s.encode()).digest()
        return base64.b64encode(md5).decode()

    @staticmethod
    def hmac_sha1(secret, message):
        h = hmac.new(secret.encode(), message.encode(), hashlib.sha1)
        return base64.b64encode(h.digest()).decode()

    @staticmethod
    def to_gmt_string(date):
        return date.strftime('%a, %d %b %Y %H:%M:%S GMT')

    async def ali_translate_async(self, text, source_language='auto', target_language='zh'):
        if isinstance(text, str):
            text = [text]
        translated_texts = []
        num_none = 0

        async with aiohttp.ClientSession() as session:
            for t in text:
                body = {
                    "FormatType": "text",
                    "SourceLanguage": source_language,
                    "TargetLanguage": target_language,
                    "SourceText": t,
                    "Scene": "general"
                }
                body_str = json.dumps(body)

                method = "POST"
                accept = "application/json"
                content_type = "application/json;charset=utf-8"
                date = self.to_gmt_string(datetime.datetime.utcnow())
                body_md5 = self.md5_base64(body_str)
                nonce = str(uuid.uuid4())

                string_to_sign = f"{method}\n{accept}\n{body_md5}\n{content_type}\n{date}\n" \
                                 f"x-acs-signature-method:HMAC-SHA1\n" \
                                 f"x-acs-signature-nonce:{nonce}\n" \
                                 f"x-acs-version:2019-01-02\n/api/translate/web/ecommerce"

                signature = self.hmac_sha1(self.conf['secretKey'], string_to_sign)
                auth_header = f"acs {self.conf['appid']}:{signature}"

                url = "http://mt.cn-hangzhou.aliyuncs.com/api/translate/web/ecommerce"
                headers = {
                    "Accept": accept,
                    "Content-Type": content_type,
                    "Content-MD5": body_md5,
                    "Date": date,
                    "Authorization": auth_header,
                    "x-acs-signature-nonce": nonce,
                    "x-acs-signature-method": "HMAC-SHA1",
                    "x-acs-version": "2019-01-02"
                }

                async with self.limiter:
                    try:
                        async with session.post(url, headers=headers, data=body_str) as response:
                            result_all = await response.text()
                            result = json.loads(result_all)
                    except Exception as e:
                        result = {'error_code': e}

                    if 'Data' in result:
                        translated_text = result['Data']['Translated']
                    else:
                        print(result)
                        translated_text = None
                        num_none += 1
                    translated_texts += [translated_text]
        return translated_texts, num_none

    async def translate(self, text, to_english=True):
        for t, t_restore in iter_lines(text, buffer=self.conf['buffer'], leave_blank=False):
            if to_english:
                t = (await self.ali_translate_async(t, target_language='en'))[0][0]
            else:
                t = (await self.ali_translate_async(t, target_language='zh'))[0][0]
            yield t_restore(t)
