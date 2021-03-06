#coding: utf-8

import gevent
from gevent import monkey
monkey.patch_all()

from gevent import queue

import os
import sys
import json
import httplib
import time
import urlparse
import functools
import logging
import uuid
import logging.config
from logging import handlers

# 参数配置开始
BASE_URI = "http://127.0.0.1:54569"
METHOD = "GET"
HEADERS = {
        "channel": "liveshow",
        "tag": "ios",
        "wait": "yes",
}
URL = "/api/poll"
# 参数配置结束


DEBUG = True
LOG_PATH = "log.log"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(name)s %(levelname)s %(asctime)s [%(pathname)s:%(lineno)d] %(message)s'
        },
    },
    'handlers': {
       'console':{
            'level':'NOTSET',
            'class':'logging.StreamHandler',
            'stream':sys.stderr,
            'formatter': 'verbose' #'simple'
        },
        'file':{
            'level':'DEBUG',
            'class':'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(os.getcwd(), LOG_PATH),
            'formatter': 'verbose',
            'maxBytes': 1024*1024*20,  # 20MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'CommonLogger': {
            'handlers': ['console', 'file'] if DEBUG else ['file'],
            'level': 'DEBUG' if DEBUG else 'DEBUG', #'INFO'
            'propagate': False,
        },
    }
}

common_logger = {
    'handlers': ['console', 'file'] if DEBUG else ['file'],
    'level': 'DEBUG' if DEBUG else 'DEBUG', #'INFO'
    'propagate': False,
}


def getlogger(logger_name=None):
    if isinstance(logger_name,str) or isinstance(logger_name,unicode):
        LOGGING['loggers'][logger_name] = common_logger
        logging.config.dictConfig(LOGGING)
        logger = logging.getLogger(logger_name)
    else:
        logging.config.dictConfig(LOGGING)
        logger = logging.getLogger("CommonLogger")
        
    return logger


logger = getlogger('Benchmark')
success = 0

jobs = []
times = []

def send_request(task_queue):
    while 1:
        task = task_queue.get()
        host, port, method, url, headers, body = task

        headers["tourid"] = str(uuid.uuid4())

        start_time = time.time()

        conn = httplib.HTTPConnection(host, port, timeout=60)
        try:
            conn.connect()
        except Exception, e:
            logger.error("can not connect to server")
            logger.error(e)

        try:
            if headers == None:
                conn.request(method, url, body, {})
            else:
		conn.request(method, url, body=body, headers=headers)
        except Exception, e:
            logger.error("send request to server error")
            logger.error(e)
            continue
#    
#        try:
#            response = conn.getresponse()
#        except Exception, e:
#            logger.error("get response from server error")
#            logger.error(e)
#            continue
#
#        if response.status != 200 and response.status != 201:
#            logger.warn("status not 200: " + str(response.status))
#            data = response.read()
#            logger.warn("got response: " + data)
#            continue
#
#        data = response.read()
#        #logger.info("got response:" + data)
#
        end_time = time.time()
        duration = end_time - start_time
        times.append(int(duration*1000))

        global success
        success += 1


def find_range(Tlist, Min, Max, Step):
    if not Tlist:
        return

    temp_list = []
    temp1_list = []
    temp2_list = []
    temp3_list = []

    for item in Tlist:
        if item > Min and item < Max:
            temp_list.append(item)

    split = Max / Step

    for i in xrange(Step):
        temp1_list.append(i*split)
    temp_list.sort()

    for i in range(len(temp1_list)-1):
        temp_dict = {}
        temp_dict["min"] = temp1_list[i]
        temp_dict["max"] = temp1_list[i+1]
        temp_dict["percent"] = 0
        temp_dict["range"] = str(temp1_list[i]) + " ~ " + str(temp1_list[i+1]) + "ms"
        temp2_list.append(temp_dict)

    temp_dict = {}
    temp_dict["min"] = temp1_list[len(temp1_list)-1]
    temp_dict["max"] = Max
    temp_dict["percent"] = 0
    temp_dict["range"] = str(temp1_list[len(temp1_list)-1]) + " ~ " + str(Max) + "ms"
    temp2_list.append(temp_dict)

    for i in temp2_list:
        for j in temp_list:
            if j >= i["min"] and j < i["max"]:
                    i["percent"] += 1
        i["percent"] = i["percent"] / float(len(Tlist))

    for i in temp2_list:
        if i["percent"] != 0.0:
            temp3_list.append(i)

    return temp3_list


if __name__ == "__main__":
    uri_parsed = urlparse.urlparse(BASE_URI) 
    host_port = uri_parsed.netloc
    try:
        HOST, PORT = host_port.split(":")
    except ValueError:
        PORT = 80

    try:
        requests = int(sys.argv[1])
    except Exception, e:
        logger.error("wrong argument for max requests, exit now...")
        sys.exit(1)

    try:
        concurrent = int(sys.argv[2])
    except Exception, e:
        logger.error("wrong argument for concurrent requests, exit now...")
        sys.exit(1)

    task_queue = queue.Queue(maxsize=concurrent)

    def boss(task_queue):
        for i in range(requests):
            task_queue.put((HOST, PORT, METHOD, URL, HEADERS, None))

    jobs.append(gevent.spawn(boss, task_queue))

    start_time = time.time()

    for i in xrange(concurrent):
        jobs.append(gevent.spawn(send_request, task_queue))

    gevent.wait()

    end_time = time.time()

    used_time = end_time - start_time

    #print "Request process:", times

    print "=" * 80
    print "HOST:", BASE_URI
    print "URL:", URL, "METHOD:", METHOD
    print "=" * 80
    print "Total: %s, Concurrent: %d" % (requests, concurrent)
    print "Success: %d, Failed: %d" % (success, (int(requests) - success))
    print "Time: %.1f, TPS: %.1f" % (used_time, success / used_time)
    print "=" * 80
    result1 = find_range(times, 0, 100, 10)
    if result1:
        for item in result1:
            print item["range"] + " : " + str(item["percent"] * 100) + "%"

    result2 = find_range(times, 100, 1000, 20)
    if result2:
        for item in result2:
            print item["range"] + " : " + str(item["percent"] * 100) + "%"

    result3 = find_range(times, 1000, 10000, 20)
    if result3:
        for item in result3:
            print item["range"] + " : " + str(item["percent"] * 100) + "%"

    print "=" * 80

    time.sleep(120)


