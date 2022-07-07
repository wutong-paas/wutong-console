#FROM wutongpaas/base-python-fastapi:3.8
FROM swr.cn-southwest-2.myhuaweicloud.com/wutong/wutong-console-base:v1.0.0-stable

COPY requirements.txt /tmp/requirements.txt
RUN apk add --no-cache --virtual .build-deps build-base libffi-dev openssl-dev python3-dev gcc libc-dev make git \
    && pip install --upgrade pip \
    && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps build-base libffi-dev openssl-dev python3-dev gcc libc-dev make git
COPY . /app
RUN chmod +x /app/bin/linux/promql-parser