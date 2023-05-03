import re
from copy import deepcopy


def return_self(t):
    return t


def get_restore_text_blank_func(front_blank: list, back_blank: list):
    front_blank = deepcopy(front_blank)
    back_blank = deepcopy(back_blank)
    def restore_text_blank(text: str):
        text_ = []
        for fb, line, bb in zip(front_blank, text.split('\n'), back_blank):
            text_.append(fb + line + bb)
        return ''.join(text_)
    return restore_text_blank


def iter_lines(text: str, buffer=None, leave_blank=False):
    """迭代获取待翻译的文本

    Args:
        text (str): 翻译文本
        buffer (int, optional): 一次请求最多字数, 0和None代表全部翻译, 负数表示按行翻译
        leave_blank (bool, optional): 是否留下空白, 不留下的话需要保证翻译之后不能改变换行数量, 留下的话翻译器可能会去除空白
            buffer != 0 才有效

    Yields:
        str, func: 待翻译文本, 翻译后的处理函数
    """
    if not buffer:
        yield text, return_self
    elif text.strip():
        start_blank = re.search('^\s*', text).group()
        end_blank = re.search('\s*$', text).group()
        middle_blank = []
        text = text.strip()

        def custom_repl(match_obj):
            middle_blank.append(match_obj.group())
            return '\n'
        text = re.sub('\s*\n\s*', custom_repl, text)

        ret_text = ''
        front_blank = []
        back_blank = []
        first = True
        for line, blank in zip(text.split('\n'), middle_blank + [end_blank]):
            if buffer > 0:  # 确定翻译器能够保留换行
                if len(ret_text + line) > buffer:
                    if leave_blank:
                        yield get_restore_text_blank_func(front_blank, back_blank)(ret_text[:-1]), return_self
                    else:
                        yield ret_text[:-1], get_restore_text_blank_func(front_blank, back_blank)
                    ret_text = ''
                    front_blank = []
                    back_blank = []
                ret_text += line + '\n'
                front_blank.append(start_blank if first else '')
                back_blank.append(blank)
            else:
                if leave_blank:
                    yield (start_blank if first else '') + line + blank, return_self
                else:
                    yield line, get_restore_text_blank_func([start_blank if first else ''], [blank])
            first = False
        if ret_text:
            if leave_blank:
                yield get_restore_text_blank_func(front_blank, back_blank)(ret_text[:-1]), return_self
            else:
                yield ret_text[:-1], get_restore_text_blank_func(front_blank, back_blank)
    else:
        if leave_blank:
            yield text, return_self
        else:
            yield '', get_restore_text_blank_func([text], [''])
