from utils import get_global_config, translate_over_filter, from_messages_get_en
import asyncio
from pprint import pprint


async def main():
    print('=====测试: translator')
    text_to_translate = '''这是一个测试: [0123456789]
[0123456789]
def abc():

    return '你好'
结束
'''
    text_to_translate_en = '''test: [0123456789]
[0123456789]
def abc():

    return 'hello'
end
'''
    for name, translator in get_global_config()['translator'].items():
        if hasattr(translator, 'translate_wrap'):
            continue
        translate = translator.translate
        print(name, '- to_english:')
        translated_text = ''.join([i async for i in translate(text_to_translate)])
        print(translated_text)
        print('-' * 10)
        print(name, ':')
        translated_text = ''.join([i async for i in translate(text_to_translate_en, to_english=False)])
        print(translated_text)
        print('-' * 20)
        
    print('=====测试: from_messages_get_en')
    marks = get_global_config()['marks']
    messages_en = from_messages_get_en([
        {
            "content": "test",
            "role": "system"
        },
        {
            "content": "你是谁？",
            "role": "user"
        },
        {
            "content": f'''
{marks["user_trans"]}hi
{marks["assistant_answer"]}hello
{marks["assistant_trans"]}你好
''',
            "role": "assistant"
        },
    ])
    pprint(messages_en)

    print('=====测试: translator_over_filter')
    text = 'Hello my world! `123`  ```abc```\nhi'
    text = ''.join([i async for i in translate_over_filter(text, translate=None)])
    print(text)
    text = ''.join([i async for i in translate_over_filter(text, translate=translate)])
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
