#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path
import os
import errno
import pymongo
import hashlib
from struct import *
from zlib import *
from conf import config

import json
from bson.objectid import ObjectId


class JSONEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)


gdb_a_tags = None


def AndroidTagsCollection(collection_name):
    global gdb_a_tags
    if gdb_a_tags is None:
        client = pymongo.MongoClient(
            config.MONGO_LIST, replicaset=config.MONGO_REPL_SET)
        gdb_a_tags = client['android_dogfood_tags']

    return gdb_a_tags[collection_name]

gdb_a = None


def AndroidCollection(collection_name):
    global gdb_a

    if gdb_a is None:
        client = pymongo.MongoClient(
            config.MONGO_LIST, replicaset=config.MONGO_REPL_SET)
        gdb_a = client['android_dogfood']

    return gdb_a[collection_name]

gdb_i = None


def IosCollection(collection_name):
    global gdb_i

    if gdb_i is None:
        client = pymongo.MongoClient(
            config.MONGO_LIST, replicaset=config.MONGO_REPL_SET)
        gdb_i = client['ios_dogfood']
    return gdb_i[collection_name]


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def get_md5(fcont):
    md5sum = hashlib.md5(fcont)
    return md5sum.hexdigest()


def get_aapt():
    if "ANDROID_HOME" in os.environ:
        rootDir = os.path.join(os.environ["ANDROID_HOME"], "build-tools")
    for path, subdir, files in os.walk(rootDir, topdown=False):
        if "aapt" in files:
            return os.path.join(path, "aapt")
    else:
        return "ANDROID_HOME not exist"


def recomposeAppInfo(ori_apps, sys_type):
    apps = []
    for app in ori_apps:
        if (app['_id'] is not None and app['_id'] != "" and app['_id'] != "null"):
            if (sys_type == u'a'):
                app['app_info']["history"] = "http://%s/%s/api/v1/apps/%s/history" % (
                    config.DF_DOMAIN, sys_type, app['app_info']['package_name'])
                apps.append(app['app_info'])
            elif(sys_type == u'i'):
                app['app_info']["history"] = "http://%s/%s/api/v1/apps/%s/history" % (
                    config.DF_DOMAIN, sys_type, app['app_info']['bundleID'])
                apps.append(app['app_info'])

    new_apps = sorted(
        apps, cmp=lambda y, x: cmp(x['timestamp'], y['timestamp']))
    return new_apps


def getNormalizedPNG(filename):
    pngheader = "\x89PNG\r\n\x1a\n"

    file = open(filename, "rb")
    oldPNG = file.read()
    file.close()

    if oldPNG[:8] != pngheader:
        return None

    newPNG = oldPNG[:8]

    chunkPos = len(newPNG)

    idatAcc = ""
    breakLoop = False

    # For each chunk in the PNG file
    while chunkPos < len(oldPNG):
        skip = False

        # Reading chunk
        chunkLength = oldPNG[chunkPos:chunkPos+4]
        chunkLength = unpack(">L", chunkLength)[0]
        chunkType = oldPNG[chunkPos+4: chunkPos+8]
        chunkData = oldPNG[chunkPos+8:chunkPos+8+chunkLength]
        chunkCRC = oldPNG[chunkPos+chunkLength+8:chunkPos+chunkLength+12]
        chunkCRC = unpack(">L", chunkCRC)[0]
        chunkPos += chunkLength + 12

        # Parsing the header chunk
        if chunkType == "IHDR":
            width = unpack(">L", chunkData[0:4])[0]
            height = unpack(">L", chunkData[4:8])[0]

        # Parsing the image chunk
        if chunkType == "IDAT":
            # Store the chunk data for later decompression
            idatAcc += chunkData
            skip = True

        # Removing CgBI chunk
        if chunkType == "CgBI":
            skip = True

        # Add all accumulated IDATA chunks
        if chunkType == "IEND":
            try:
                # Uncompressing the image chunk
                bufSize = width * height * 4 + height
                chunkData = decompress(idatAcc, -15, bufSize)

            except Exception, e:
                # The PNG image is normalized
                logging.exception(e.message)
                return None

            chunkType = "IDAT"

            # Swapping red & blue bytes for each pixel
            newdata = ""
            for y in xrange(height):
                i = len(newdata)
                newdata += chunkData[i]
                for x in xrange(width):
                    i = len(newdata)
                    newdata += chunkData[i+2]
                    newdata += chunkData[i+1]
                    newdata += chunkData[i+0]
                    newdata += chunkData[i+3]

            # Compressing the image chunk
            chunkData = newdata
            chunkData = compress(chunkData)
            chunkLength = len(chunkData)
            chunkCRC = crc32(chunkType)
            chunkCRC = crc32(chunkData, chunkCRC)
            chunkCRC = (chunkCRC + 0x100000000) % 0x100000000
            breakLoop = True

        if not skip:
            newPNG += pack(">L", chunkLength)
            newPNG += chunkType
            if chunkLength > 0:
                newPNG += chunkData
            newPNG += pack(">L", chunkCRC)
        if breakLoop:
            break

    return newPNG


def updatePNG(filename):
    data = getNormalizedPNG(filename)
    if data is not None:
        file = open(filename, "wb")
        file.write(data)
        file.close()
        return True
    return data
