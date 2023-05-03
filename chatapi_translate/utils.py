import commentjson as json
import re
import random
import string
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import logging

from .translator import get_translator

global_config = None


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, file_path):
        self.file_path = file_path
        self.last_modified_time = 0

    def on_modified(self, event):
        if not event.is_directory and event.src_path == self.file_path:
            current_time = time.time()
            if current_time - self.last_modified_time > 2:
                self.load_config()
                self.last_modified_time = current_time

    def load_config(self):
        global global_config
        try:
            with open(self.file_path, 'r', encoding='utf8') as file:
                global_config = json.load(file)
                for k, conf in global_config['translator'].items():
                    global_config['translator'][k] = get_translator(conf)
                print("Configuration file reloaded.")
        except BaseException as e:
            logging.warning('重载配置配置文件失败!', str(e))


def get_global_config(file_path='config.jsonc'):
    global global_config
    if global_config is None:
        event_handler = ConfigFileHandler(file_path)
        event_handler.load_config()
        observer = Observer()
        observer.schedule(event_handler, path=file_path, recursive=False)
        observer.start()
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


def generate_random_id(length=10, wrap=True, only_digits=False):
    if only_digits:
        ss = string.digits
    else:
        ss = string.ascii_letters + string.digits
    s = ''.join(random.choices(ss, k=length))
    if wrap:
        return '[' + s + ']'
    else:
        return s


async def translate_over_filter(text, translate, role="assistant"):
    # 过滤文本
    filter_re = get_global_config()['filter']['re']['del_trans'][role]
    text = re.sub(filter_re, '', text) if filter_re else text
    id_origin = []  # [(id,原始字符串),..]

    def custom_repl(match_obj):
        matched_substring = match_obj.group()
        id_ = generate_random_id(10, only_digits=True)
        id_origin.append((id_, matched_substring))
        return id_  # 返回要替换的字符串
    filter_re = get_global_config()['filter']['re']['no_trans'][role]
    filtered_text = re.sub(filter_re, custom_repl, text) if filter_re else text

    def text_restore(t):  # 还原翻译前的过滤文本
        if len(t) >= 12:
            for id_, sub in id_origin:
                t = t.replace(id_, sub)
        return t
    # 翻译
    if translate is not None:
        to_english = role != "assistant"
        async for translated_text in translate(filtered_text, to_english=to_english):
            yield text_restore(translated_text)
    else:
        print(filtered_text)  # 测试
        yield text_restore(filtered_text)


async def response_stream(client_stream, modify_func=None):
    async with client_stream as response:
        async for line in response.aiter_lines():
            line = line.strip()
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
                    if d:
                        yield json.dumps(d, ensure_ascii=False)
            else:
                yield json.dumps(data, ensure_ascii=False)


def filter_messages_and_trigger(messages):  # 用于不翻译的信息
    filtered_messages = []
    no_trans_trigger = get_global_config()['filter']['no_trans_trigger']

    marks = get_global_config()['marks']
    u_trans = re.escape(marks["user_trans"])
    a_answer = re.escape(marks["assistant_answer"])
    a_trans = re.escape(marks["assistant_trans"])
    re_end = f'(?={u_trans}|{a_answer}|{a_trans}|$)'

    for message in messages:
        if message['role'] != 'assistant':
            if no_trans_trigger:
                message['content'] = message['content'].replace(no_trans_trigger, '')
            filtered_messages.append(message)
        else:
            assistant = re.search(f'(?<={a_answer})[\w\W]+?{re_end}', message['content'])
            if assistant:
                filtered_messages.append({'role': 'assistant', 'content': assistant.group()})
            else:
                filtered_messages.append(message)
    return filtered_messages


def has_no_trans_trigger(messages):  # 判断是否不要翻译
    no_trans_trigger = get_global_config()['filter']['no_trans_trigger']
    if not no_trans_trigger:
        return False
    for message in messages:
        if message['role'] == 'assistant':
            continue
        if no_trans_trigger in message['content']:
            return True
    return False


def generate_stream_response_start(id_str, model_name='gpt-3.5-turbo'):
    ret = {"id": id_str, "object": "chat.completion.chunk", "created": int(
        time.time()), "model": model_name, "choices": [{"delta": {"role": "assistant"}, "index": 0, "finish_reason": None}]}
    return ret


def generate_stream_response(content: str, id_str, model_name='gpt-3.5-turbo'):
    ret = {
        "id": id_str,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"delta": {"content": content}, "index": 0, "finish_reason": None}]}
    return ret
