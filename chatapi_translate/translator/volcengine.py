import aiohttp
import hashlib
import hmac
import json
from aiolimiter import AsyncLimiter
from datetime import datetime
from urllib.parse import quote
from .utils import iter_lines


class SignerV4(object):
    # https://github.com/volcengine/volcengine-python-sdk/blob/master/volcenginesdkcore/signv4.py
    @staticmethod
    def sign(path, method, headers, body, query, ak, sk, region, service):
        if path == '':
            path = '/'
        if method != 'GET' and not ('Content-Type' in headers):
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
        format_date = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        headers['X-Date'] = format_date

        body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
        headers['X-Content-Sha256'] = body_hash

        signed_headers = dict()
        for key in headers:
            if key in ['Content-Type', 'Content-Md5', 'Host'] or key.startswith('X-'):
                signed_headers[key.lower()] = headers[key]

        if 'host' in signed_headers:
            v = signed_headers['host']
            if v.find(':') != -1:
                split = v.split(':')
                port = split[1]
                if str(port) == '80' or str(port) == '443':
                    signed_headers['host'] = split[0]

        signed_str = ''
        for key in sorted(signed_headers.keys()):
            signed_str += key + ':' + signed_headers[key] + '\n'

        signed_headers_string = ';'.join(sorted(signed_headers.keys()))

        canonical_request = '\n'.join(
            [method, path, SignerV4.canonical_query(dict(query)), signed_str, signed_headers_string, body_hash])
        credential_scope = '/'.join([format_date[:8], region, service, 'request'])
        signing_str = '\n'.join(['HMAC-SHA256', format_date, credential_scope,
                                 hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()])
        signing_key = SignerV4.get_signing_secret_key_v4(sk, format_date[:8], region, service)

        signature = hmac.new(signing_key, signing_str.encode('utf-8'), hashlib.sha256).hexdigest()

        credential = ak + '/' + credential_scope
        headers[
            'Authorization'] = 'HMAC-SHA256' + ' Credential=' + credential + ', SignedHeaders=' + \
                               signed_headers_string + ', Signature=' + signature
        return

    @staticmethod
    def canonical_query(query):
        res = []
        for key in query:
            value = str(query[key])
            res.append((quote(key, safe='-_.~'), quote(value, safe='-_.~')))
        sorted_key_vals = []
        for key, value in sorted(res):
            sorted_key_vals.append('%s=%s' % (key, value))
        return '&'.join(sorted_key_vals)

    @staticmethod
    def get_signing_secret_key_v4(sk, date, region, service):
        kdate = SignerV4.hmac_sha256(sk.encode('utf-8'), date)
        kregion = SignerV4.hmac_sha256(kdate, region)
        kservice = SignerV4.hmac_sha256(kregion, service)
        return SignerV4.hmac_sha256(kservice, 'request')

    @staticmethod
    def hmac_sha256(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()


class Translator:
    def __init__(self, conf):
        self.conf = conf
        self.limiter = AsyncLimiter(conf['qps'], 1)

    async def volcengine_translate_async(self, text_list, source_lang=None, target_lang="zh"):
        action = "TranslateText"
        version = "2020-06-01"
        region = "cn-north-1"
        service = "translate"
        host = "open.volcengineapi.com"
        content_type = "application/json; charset=utf-8"
        url = f"https://{host}/"

        payload = {
            "TargetLanguage": target_lang,
            "TextList": text_list
        }
        if source_lang:
            payload['SourceLanguage'] = source_lang

        payload_json = json.dumps(payload)
        headers = {
            "Content-Type": content_type
        }

        query = {
            "Action": action,
            "Version": version
        }

        SignerV4.sign("/", "POST", headers, payload_json, query,
                      self.conf['accessKey'], self.conf['secretKey'], region, service)

        async with aiohttp.ClientSession() as session:
            async with self.limiter:
                async with session.post(url, headers=headers, params=query, data=payload_json) as response:
                    result = await response.json()

        return result

    async def translate(self, text, to_english=True):
        target_lang = 'en' if to_english else 'zh'
        for t, t_restore in iter_lines(text, buffer=self.conf['buffer'], leave_blank=False):
            response = await self.volcengine_translate_async([t], target_lang=target_lang)
            try:
                t = response['TranslationList'][0]['Translation']
            except:
                print(response)
                t = ''
            yield t_restore(t)
