from .deepl import Translator as translator_deepl
from .baidu import Translator as translator_baidu
from .tencent import Translator as translator_tencent


def get_translator(conf):
    if conf['name'] == 'deepl':
        return translator_deepl(conf)
    elif conf['name'] == 'baidu':
        return translator_baidu(conf)
    elif conf['name'] == 'tencent':
        return translator_tencent(conf)
    else:
        raise NameError('未知翻译器！')
