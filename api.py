from copy import deepcopy
import traceback
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from fastapi.responses import Response
from fastapi import FastAPI, Request, status, HTTPException
import httpx
from urllib.parse import urlparse
import logging

from utils import get_global_config, from_messages_get_en, translate_over_filter, response_stream

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
    # 非流式传输/自动标题的情况不使用翻译
    if (
        body is None
        or "stream" not in body
        or not body["stream"]
        or not get_global_config()["filter"]["auto_title_trans"]
        and body["messages"]
        and (
            body["messages"][-1]["role"] != "user"
            or len(body["messages"]) > 1
            and body["messages"][-1]["role"] == body["messages"][-2]["role"] == "user"
        )
    ):
        try:
            # print(headers)
            # print(body)
            if body["stream"]:
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
    translate = get_global_config()['translator'][t_name].translate
    q_t = await translate_over_filter(question, translate, role="user")  # 翻译
    messages = from_messages_get_en(body["messages"])  # 只取英文部分
    # 修改返回信息
    info = {
        'contents': [],  # 返回的内容
        'first_return': False,  # 第一次构建用户的翻译结果
    }
    marks = get_global_config()['marks']

    async def modify_func(data):
        if 'choices' in data:
            info['contents'] += [c['delta']['content']
                                 for c in data['choices'] if 'delta' in c and 'content' in c['delta']]
            # 构建用户的翻译结果
            if not info['first_return'] and data['choices'] and 'content' in data['choices'][-1]['delta']:
                prefix = marks["user_trans"] + q_t + marks["assistant_answer"]
                data['choices'][-1]['delta']['content'] = prefix + data['choices'][-1]['delta']['content']
                info['first_return'] = True
            # 停止前再翻译助理
            if data['choices'][0]['finish_reason'] == 'stop':
                data_ = deepcopy(data)
                data_['choices'][0]['finish_reason'] = None
                data_['choices'][0]['delta']['content'] = marks["assistant_trans"]
                yield data_
                content = await translate_over_filter(''.join(info['contents']), translate, role="assistant")
                data_['choices'][0]['delta']['content'] = content
                yield data_
        yield data
    # 构建请求
    body['messages'] = messages + [{'role': 'user', 'content': q_t}]
    # print(body)
    client_stream = client.stream("POST", url, headers=headers, json=body, timeout=360)
    return EventSourceResponse(response_stream(client_stream, modify_func), ping=10000)


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


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=7100)
