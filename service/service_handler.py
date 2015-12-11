# -*- coding: utf-8 -*-

import datetime
import time
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, options
from libs.apk_parser import ApkParser
from libs.ipa_parser import IpaParser
from libs.utils import JSONEncoder, AndroidCollection, IosCollection, recomposeAppInfo, AndroidTagsCollection
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename='logging.log',
                    filemode='a')

define("port", default=8080, help="run on the given port", type=int)


class Application(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r"/a/api/v1/apps/(\w+\.\w+.*)/history", AndroidAppRecentHandler),
            (r"/a/api/v1/apps/(\w+\.\w+.*)", AndroidAppLatestHandler),
            (r"/a/api/v1/(\w+)/upload", ApkUploadHandler),
            (r"/a/api/v1/all/latest", AndroidAllLatestHandler),
            (r"/a/api/v1/add/tag", AndroidAddTagHandler),
            (r"/a/api/v1/check/tags", AndroidCheckTagHandler),
            (r"/i/api/v1/apps/(\w+.*)/history", IosAppRecentHandler),
            (r"/i/api/v1/apps/(\w+.*)", IosAppLatestHandler),
            (r"/i/api/v1/(\w+)/upload", IpaUploadHandler),
            (r"/i/api/v1/all/latest", IosAllLatestHandler),
        ]
        settings = dict(debug=True)
        tornado.web.Application.__init__(self, handlers, **settings)


class AndroidAddTagHandler(tornado.web.RequestHandler):

    def post(self):
        r = dict()
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'product_name' not in kwargs:
            r['msg'] = "error: need product_name!"
        if 'git_tag' not in kwargs:
            r['msg'] = "error: need git_tag!"
        if 'msg' not in r:
            timestamp = int(time.time())
            dateArray = datetime.datetime.utcfromtimestamp(timestamp) + datetime.timedelta(hours=8)
            otherStyleTime = dateArray.strftime("%Y-%m-%d %H:%M:%S")
            kwargs['timestamp'] = timestamp
            kwargs['time'] = otherStyleTime
            coll = AndroidTagsCollection('meta')
            coll.insert_one(kwargs)
            r['msg'] = 'success'
        self.write(r)


class AndroidCheckTagHandler(tornado.web.RequestHandler):

    def get(self):
        kwargs = dict()
        tags = list()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        coll = AndroidTagsCollection('meta')
        docs = coll.find(kwargs).sort([("timestamp", -1)])
        for doc in docs:
            tags.append(doc)
        self.write(JSONEncoder().encode(tags))


class ApkUploadHandler(tornado.web.RequestHandler):

    def post(self, path):
        fileinfo = self.request.files['file'][0]
        filename = fileinfo['filename']
        if filename[-4:] == u'.apk':
            r = ApkParser(fileinfo, path).upload_apk()
        else:
            r = dict()
            r['msg'] = "ERROR: PLEASE UPLOAD APK FILE!"
        self.write(r)


class IpaUploadHandler(tornado.web.RequestHandler):

    def post(self, type):
        fileinfo = self.request.files['file'][0]
        filename = fileinfo['filename']
        if filename[-4:] == u'.ipa':
            r = IpaParser(fileinfo, type).upload_ipa()
        else:
            r = dict()
            r['msg'] = "ERROR: PLEASE UPLOAD IPA FILE!"
        self.write(r)


class AndroidAllLatestHandler(tornado.web.RequestHandler):

    def get(self):
        coll = AndroidCollection('meta')
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'type' in kwargs:
            show_type = kwargs['type']
        else:
            show_type = "dogfood"
        pipeline = [{"$match": {"type": show_type}},
                    {"$sort": {"timestamp": -1}},
                    {"$group": {"_id": "$package_name", "app_info": {"$first": "$$ROOT"}}},
                    ]
        ori_apps = list(coll.aggregate(pipeline))
        print ori_apps
        apps = recomposeAppInfo(ori_apps, u"a")
        self.write(JSONEncoder().encode(apps))


class AndroidAppRecentHandler(tornado.web.RequestHandler):

    def get(self, pkg_name):
        coll = AndroidCollection('meta')
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'type' in kwargs:
            show_type = kwargs['type']
        else:
            show_type = "dogfood"
        pipeline = [{"$match": {"package_name": pkg_name, "type": show_type}},
                    {"$sort": {"timestamp": -1}},
                    {"$limit": 10},
                    {"$group": {"_id": "$downpath", "app_info": {"$first": "$$ROOT"}}},
                    ]
        ori_apps = list(coll.aggregate(pipeline))
        apps = recomposeAppInfo(ori_apps, u"a")
        self.write(JSONEncoder().encode(apps))


class AndroidAppLatestHandler(tornado.web.RequestHandler):

    def get(self, pkg_name):
        coll = AndroidCollection('meta')
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'type' in kwargs:
            show_type = kwargs['type']
        else:
            show_type = "dogfood"
        pipeline = [{"$match": {"package_name": pkg_name, "type": show_type}},
                    {"$sort": {"version_code": -1}},
                    {"$limit": 1},
                    {"$group": {"_id": "$md5", "app_info": {"$first": "$$ROOT"}}},
                    ]
        ori_apps = list(coll.aggregate(pipeline))
        apps = recomposeAppInfo(ori_apps, u"a")
        self.write(JSONEncoder().encode(apps))


class IosAllLatestHandler(tornado.web.RequestHandler):

    def get(self):
        coll = IosCollection('meta')
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'type' in kwargs:
            show_type = kwargs['type']
        else:
            show_type = "dogfood"
        pipeline = [{"$match": {"type": show_type}},
                    {"$sort": {"timestamp": -1}},
                    {"$group": {"_id": "$bundleID", "app_info": {"$first": "$$ROOT"}}},
                    ]
        ori_apps = list(coll.aggregate(pipeline))
        apps = recomposeAppInfo(ori_apps, u"i")
        self.write(JSONEncoder().encode(apps))


class IosAppRecentHandler(tornado.web.RequestHandler):

    def get(self, bundle_id):
        coll = IosCollection('meta')
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'type' in kwargs:
            show_type = kwargs['type']
        else:
            show_type = "dogfood"
        pipeline = [{"$match": {"bundleID": bundle_id, "type": show_type}},
                    {"$sort": {"timestamp": -1}},
                    {"$limit": 10},
                    {"$group": {"_id": "$downpath", "app_info": {"$first": "$$ROOT"}}},
                    ]
        ori_apps = list(coll.aggregate(pipeline))
        logging.info(ori_apps)
        apps = recomposeAppInfo(ori_apps, u"i")
        self.write(JSONEncoder().encode(apps))


class IosAppLatestHandler(tornado.web.RequestHandler):

    def get(self, bundle_id):
        coll = IosCollection('meta')
        kwargs = dict()
        for key in self.request.arguments:
            kwargs[key] = self.get_argument(key)
        if 'type' in kwargs:
            show_type = kwargs['type']
        else:
            show_type = "dogfood"
        pipeline = [{"$match": {"bundleID": bundle_id, "type": show_type}},
                    {"$sort": {"timestamp": -1}},
                    {"$limit": 1},
                    {"$group": {"_id": "$md5", "app_info": {"$first": "$$ROOT"}}},
                    ]
        ori_apps = list(coll.aggregate(pipeline))
        apps = recomposeAppInfo(ori_apps, u"i")
        self.write(JSONEncoder().encode(apps))


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
