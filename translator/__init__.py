from .deepl import Translator as translator_deepl
from .baidu import Translator as translator_baidu
from .tencent import Translator as translator_tencent
from .ali import Translator as translator_ali
from .caiyun import Translator as translator_caiyun
from .volcengine import Translator as translator_volcengine
from .google import Translator as translator_google


def get_translator(conf):
    if conf['name'] == 'deepl':
        return translator_deepl(conf)
    elif conf['name'] == 'baidu':
        return translator_baidu(conf)
    elif conf['name'] == 'tencent':
        return translator_tencent(conf)
    elif conf['name'] == 'ali':
        return translator_ali(conf)
    elif conf['name'] == 'caiyun':
        return translator_caiyun(conf)
    elif conf['name'] == 'volcengine':
        return translator_volcengine(conf)
    elif conf['name'] == 'google':
        return translator_google(conf)
    else:
        raise NameError('未知翻译器！')
