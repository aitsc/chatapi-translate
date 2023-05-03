from copy import deepcopy
import traceback
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from fastapi.responses import Response
from fastapi import FastAPI, Request, status, HTTPException
import httpx
from urllib.parse import urlparse
import json
import argparse
import os
import logging

from .utils import get_global_config, from_messages_get_en, translate_over_filter, response_stream, has_no_trans_trigger, filter_messages_and_trigger, generate_stream_response, generate_stream_response_start, generate_random_id

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.post("/v1/chat/completions")
async def completions(request: Request):
    try:
        body = await request.json()
    except:
        body = None
    headers = {k.lower(): v for k, v in request.headers.items()}
    url = get_global_config()["endpoint"] + '/v1/chat/completions'
    headers["host"] = urlparse(url).netloc
    del headers['content-length']
    client = httpx.AsyncClient()
    # 非流式传输/自动标题/触发词不翻译等情况不使用翻译
    if (
        body is None
        or "model" not in body
        or "messages" not in body
        or "stream" not in body
        or not body["stream"]
        or has_no_trans_trigger(body["messages"])
        or not get_global_config()["filter"]["auto_title_trans"]
        and body["messages"]
        and (
            body["messages"][-1]["role"] != "user"
            or len(body["messages"]) > 1
            and body["messages"][-1]["role"] == body["messages"][-2]["role"] == "user"
        )
    ):
        try:
            if 'messages' in body:
                body["messages"] = filter_messages_and_trigger(body["messages"])
            if 'stream' in body and body["stream"]:
                client_stream = client.stream("POST", url, headers=headers, json=body, timeout=360)
                return EventSourceResponse(response_stream(client_stream), ping=10000)
            else:
                response = await client.post(url, headers=headers, json=body)
                return Response(
                    response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.headers.get("Content-Type"),
                )
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
    # 获取问题和消息
    question = ''
    for message in body["messages"][::-1]:
        if message['role'] == 'user':
            question += message['content'] + '\n'  # 合并所有连续问题
        else:
            break
    question = question.strip()
    if not question:  # 没有问题
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No Question Found")
    if headers['authorization'] in get_global_config()['key_translator']:  # 翻译器
        t_name = get_global_config()['key_translator'][headers['authorization']]
    else:
        t_name = get_global_config()['key_translator']['']
    messages = from_messages_get_en(body["messages"])  # 只取英文部分
    translator = get_global_config()['translator'][t_name]
    # 修改返回信息
    info = {
        'contents': [],  # 返回的内容
    }
    marks = get_global_config()['marks']
    id_str = 'chatcmpl-' + generate_random_id(29, wrap=False)

    async def modify_func(data):
        if 'choices' in data and data['choices']:
            info['contents'] += [c['delta']['content']
                                 for c in data['choices'] if 'delta' in c and 'content' in c['delta']]
            data['model'] = body['model']
            data['id'] = id_str
            # 停止前再翻译助理
            if data['choices'][0]['finish_reason'] == 'stop':
                data_ = deepcopy(data)
                data_['choices'][0]['finish_reason'] = None
                data_['choices'][0]['delta']['content'] = marks["assistant_trans"]
                yield data_
                contents = ''.join(info['contents'])
                if hasattr(translator, 'translate_wrap'):
                    translate = await translator.translate_wrap(url, body, headers, context=body['messages'] + [
                        {'role': 'assistant', 'content': contents}])
                else:
                    translate = translator.translate
                async for content in translate_over_filter(contents, translate, role="assistant"):
                    data_['choices'][0]['delta']['content'] = content
                    yield data_
                yield data
            elif 'content' in data['choices'][0]['delta']:
                yield data

    async def response_func():
        # 开头
        yield json.dumps(generate_stream_response_start(id_str, body['model']), ensure_ascii=False)
        yield json.dumps(generate_stream_response(marks["user_trans"], id_str, body['model']), ensure_ascii=False)
        q_t_all = ''
        # 提问翻译
        if hasattr(translator, 'translate_wrap'):
            translate = await translator.translate_wrap(url, body, headers, context=messages)
        else:
            translate = translator.translate
        async for q_t in translate_over_filter(question, translate, role="user"):
            q_t_all += q_t
            yield json.dumps(generate_stream_response(q_t, id_str, body['model']), ensure_ascii=False)
        yield json.dumps(generate_stream_response(marks["assistant_answer"], id_str, body['model']), ensure_ascii=False)
        # 构建请求
        body['messages'] = messages + [{'role': 'user', 'content': q_t_all}]
        client_stream = client.stream("POST", url, headers=headers, json=body, timeout=360)
        # 助理回答
        async for resp in response_stream(client_stream, modify_func):
            yield resp
    return EventSourceResponse(response_func(), ping=10000)


@app.route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def catch_all(request: Request):
    url = f"{get_global_config()['endpoint']}{request.url.path}"
    method = request.method
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    headers["host"] = urlparse(url).netloc

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            url,
            headers=headers,
            content=body,
        )
        return Response(response.content, status_code=response.status_code, headers=dict(response.headers))
    
    
def main():
    parser = argparse.ArgumentParser(description='Run the web server with specified port.')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host address to run the server on (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=7100, help='Port number to run the server on (default: 7100)')
    parser.add_argument('--config', type=str, default='config.jsonc',
                        help='configuration file path, content format reference: https://github.com/aitsc/chatapi-translate/blob/master/config_example.jsonc')
    args = parser.parse_args()
    if not os.path.exists(args.config):
        print('需要用 --config 命令行参数指定存在的配置文件路径!\n样例模版请参考: https://github.com/aitsc/chatapi-translate/blob/master/config_example.jsonc')
        return
    get_global_config(args.config)
    uvicorn.run(app, host=args.host, port=args.port)
