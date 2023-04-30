import commentjson as json
import re
import random
import string
from translator import get_translator

global_config = None


def get_global_config():
    global global_config
    if global_config is None:
        with open('config.jsonc', 'r', encoding='utf8') as r:
            global_config = json.load(r)
        for k, conf in global_config['translator'].items():
            global_config['translator'][k] = get_translator(conf)
    return global_config


def from_messages_get_en(messages):
    messages_en = []
    marks = get_global_config()['marks']
    u_trans = re.escape(marks["user_trans"])
    a_answer = re.escape(marks["assistant_answer"])
    a_trans = re.escape(marks["assistant_trans"])
    re_end = f'(?={u_trans}|{a_answer}|{a_trans}|$)'
    for message in messages:
        if message['role'] == 'system':
            messages_en.append(message)
        elif message['role'] == 'assistant':
            user = re.search(f'(?<={u_trans})[\w\W]+?{re_end}', message['content'])
            assistant = re.search(f'(?<={a_answer})[\w\W]+?{re_end}', message['content'])
            if user:
                messages_en.append({'role': 'user', 'content': user.group()})
            if assistant:
                messages_en.append({'role': 'assistant', 'content': assistant.group()})
    return messages_en


def generate_random_id(length=10):
    return '[' + ''.join(random.choices(string.ascii_letters + string.digits, k=length)) + ']'


async def translate_over_filter(text, translate, role="assistant", restore=True):
    # 过滤文本
    filter_re = get_global_config()['filter']['re']['del_trans'][role]
    text = re.sub(filter_re, '', text) if filter_re else text
    id_origin = []  # [(id,原始字符串),..]

    def custom_repl(match_obj):
        matched_substring = match_obj.group()
        id_ = generate_random_id(10)
        id_origin.append((id_, matched_substring))
        return id_  # 返回要替换的字符串
    filter_re = get_global_config()['filter']['re']['no_trans'][role]
    filtered_text = re.sub(filter_re, custom_repl, text) if filter_re else text
    # 翻译
    if translate is not None:
        to_english = role != "assistant"
        translated_text = await translate(filtered_text, to_english=to_english)
    else:
        print(filtered_text)  # 测试
        translated_text = filtered_text
    # 还原翻译前的过滤文本
    final_text = translated_text
    for id_, sub in id_origin:
        if restore:
            final_text = final_text.replace(id_, sub)
        else:
            final_text = final_text.replace(id_, '')
    return final_text


async def response_stream(client_stream, modify_func=None):
    async with client_stream as response:
        async for line in response.aiter_lines():
            if not line or line is None:
                continue
            if line.startswith("data: "):
                line = line[6:]
            if line == "[DONE]":
                yield line
                break
            data = json.loads(line)
            if modify_func is not None:
                async for d in modify_func(data):
                    yield json.dumps(d, ensure_ascii=False)
            else:
                yield json.dumps(data, ensure_ascii=False)
