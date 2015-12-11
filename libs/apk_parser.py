#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os.path
import random
import re
import time
import zipfile
from conf import config
from libs.utils import get_md5, get_aapt, mkdir_p, AndroidCollection


class ApkParser(object):

    def __init__(self, fileinfo, path):
        self.type = path
        self.coll = AndroidCollection('meta')
        self.filename = fileinfo['filename']
        self.timestamp = int(time.time())
        self.apk_path = config.APKS_DIR + "/" + path + "/" + \
            str(self.timestamp) + '_' + get_md5(str(random.random()))[0:9]
        mkdir_p(self.apk_path)
        self.apk_file = self.apk_path + "/" + self.filename
        with open(self.apk_file, 'wb') as f:
            f.write(fileinfo.body)

    def upload_apk(self):
        ret = dict()
        kwargs = dict()
        if not os.path.isfile(self.apk_file):
            ret['msg'] = "ERROR: APK FILE UPLOAD FAIL!"
            return ret

        # parse apk_info
        zip_file = zipfile.ZipFile(self.apk_file)
        apk_info = os.popen(get_aapt() + " dump badging " + self.apk_file).read()
        label = re.search(r"label='(.*?)'", apk_info).group(1)
        icon_name = re.search(r"application-icon-480:'(.*png?)'", apk_info).group(1)
        package_name = re.search(r"package:.*name='(.*?)'", apk_info).group(1)
        version_name = re.search(r"versionName='(.*?)'", apk_info).group(1)
        version_code = re.search(r"versionCode='(.*?)'", apk_info).group(1)
        version = version_name + "." + version_code
        apk_md5 = get_md5(open(self.apk_file, 'r').read())
        apk_size = os.path.getsize(self.apk_file)
        icon_file = zip_file.extract(icon_name, self.apk_path)
        cmd = "cp %s %s/icon.png" % (icon_file, self.apk_path)
        os.popen(cmd)

        # generate qrcode icon
        self.gen_qrcode(package_name)

        date_array = datetime.datetime.fromtimestamp(self.timestamp)
        other_style_time = date_array.strftime("%m/%d/%Y %H:%M:%S")

        kwargs['timestamp'] = self.timestamp
        kwargs['build_time'] = other_style_time
        kwargs['label'] = label
        kwargs['filename'] = self.filename
        kwargs['package_name'] = package_name
        kwargs['version'] = version
        kwargs['version_name'] = version_name
        kwargs['version_code'] = version_code
        kwargs['md5'] = apk_md5
        kwargs['size'] = apk_size
        kwargs['type'] = self.type
        kwargs['icon_path'] = "http://%s%s/icon.png" % \
            (config.DF_DOMAIN, self.apk_path)
        kwargs['qr_icon_path'] = "http://%s%s/qr_icon.png" % \
            (config.DF_DOMAIN, self.apk_path)
        kwargs['downpath'] = "http://%s%s/%s" % \
            (config.DF_DOMAIN, self.apk_path, self.filename)
        kwargs['type'] = self.type

        self.coll.insert_one(kwargs)
        ret["msg"] = "success"
        return ret

    def gen_qrcode(self, package_name):
        import qrcode
        path = ""
        if self.type == "dogfood":
            path = ""
        else:
            path = "/" + self.type
        url = "http://" + config.DF_DOMAIN + path + "/a/" + package_name
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        qr_icon_path = self.apk_path + "/qr_icon.png"
        qr.make_image().save(qr_icon_path)
