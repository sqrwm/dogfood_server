#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import tempfile
import zipfile
import datetime
import time
import random
import logging
from urllib import quote

from conf import constants, config
from libs.biplist import readPlist
from libs.utils import get_md5, mkdir_p, IosCollection, updatePNG

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
PROJ_PATH = os.path.dirname(os.path.realpath(SCRIPT_PATH))


class IpaParser(object):
    plist_temp_file = None
    plist_info_list = None

    def __init__(self, fileinfo, path):
        self.type = path
        self.coll = IosCollection('meta')
        self.filename = fileinfo['filename']
        self.timestamp = int(time.time())
        date_array = datetime.datetime.fromtimestamp(self.timestamp)
        self.uploadTime = date_array.strftime("%m/%d/%Y %H:%M:%S")

        self.ipa_path = config.IPAS_DIR + "/" + path + "/" + \
            str(self.timestamp) + "_" + get_md5(str(random.random()))[0:9]
        self.downpath = "http://%s%s/%s" % \
            (config.DF_DOMAIN, self.ipa_path, quote(self.filename.encode('utf8')))
        self.plistpath = self.ipa_path + "/" + constants.PRODUCT_PLIST
        mkdir_p(self.ipa_path)
        self.ipa_file = self.ipa_path + "/" + self.filename
        with open(self.ipa_file, 'wb') as f:
            f.write(fileinfo.body)
        with open(self.ipa_file, 'r') as f:
            self.ipa_md5 = get_md5(f.read())
        self._check()

    def _get_plist_temp_file(self):
        self.plist_temp_file = ''

        zfile = zipfile.ZipFile(self.ipa_file)
        zip_name_list = zfile.namelist()
        for name in zip_name_list:
            if ".app/Info.plist" in name:
                tup = tempfile.mkstemp(suffix='.plist')
                fd = os.fdopen(tup[0], "w")
                fd.write(zfile.read(name))
                fd.close()
                self.plist_temp_file = tup[1]
        zfile.close()

        return self.plist_temp_file

    def _parse_plist(self):
        try:
            if self.plist_temp_file is None:
                self._get_plist_temp_file()

            if self.plist_temp_file == '':
                self.plist_info_list = {}
                return False

            self.plist_info_list = readPlist(self.plist_temp_file)
            os.remove(self.plist_temp_file)
            return self.plist_info_list
        except Exception, e:
            print "Not a plist:", e
            self.plist_info_list = {}
            return False

    def _check(self):
        if self.plist_info_list is None:
            self._parse_plist()

    def all_info(self):
        self._check()
        return self.plist_info_list

    def app_name(self):
        self._check()
        if 'CFBundleDisplayName' in self.plist_info_list:
            return self.plist_info_list['CFBundleDisplayName']
        elif 'CFBundleName' in self.plist_info_list:
            return self.plist_info_list['CFBundleName']
        return None

    def bundle_identifier(self):
        self._check()
        if 'CFBundleIdentifier' in self.plist_info_list:
            return self.plist_info_list['CFBundleIdentifier']
        return ''

    def target_os_version(self):
        self._check()
        if 'DTPlatformVersion' in self.plist_info_list:
            return re.findall('[\d\.]*', self.plist_info_list['DTPlatformVersion'])[0]
        return ''

    def minimum_os_version(self):
        self._check()
        if 'MinimumOSVersion' in self.plist_info_list:
            return re.findall('[\d\.]*', self.plist_info_list['MinimumOSVersion'])[0]
        return ''

    def bundle_short_version(self):
        self._check()
        if 'CFBundleShortVersionString' in self.plist_info_list:
            return self.plist_info_list['CFBundleShortVersionString']
        return ''

    def bundle_version(self):
        self._check()
        if 'CFBundleVersion' in self.plist_info_list:
            return self.plist_info_list['CFBundleVersion']
        return ''

    def icon_file_name(self):
        if 'CFBundleIcons' in self.plist_info_list and \
            'CFBundlePrimaryIcon' in self.plist_info_list["CFBundleIcons"] and \
                'CFBundleIconFiles' in self.plist_info_list["CFBundleIcons"]["CFBundlePrimaryIcon"]:
            icons = self.plist_info_list["CFBundleIcons"]["CFBundlePrimaryIcon"]['CFBundleIconFiles']
            if icons is not None and len(icons) > 0:
                return icons[len(icons) - 1]
        elif 'CFBundleIcons~ipad' in self.plist_info_list and \
            'CFBundlePrimaryIcon' in self.plist_info_list["CFBundleIcons~ipad"] and \
                'CFBundleIconFiles' in self.plist_info_list["CFBundleIcons~ipad"]["CFBundlePrimaryIcon"]:
            icons = self.plist_info_list["CFBundleIcons~ipad"]["CFBundlePrimaryIcon"]['CFBundleIconFiles']
            if icons is not None and len(icons) > 0:
                return icons[len(icons) - 1]
        else:
            return False

    def icon_file_path(self):
        icon_file_name = self.icon_file_name()
        if icon_file_name:
            zfile = zipfile.ZipFile(self.ipa_file)
            zip_name_list = zfile.namelist()
            for name in zip_name_list:
                tempkey = ".app/" + icon_file_name
                if tempkey in name:
                    zfile.close()
                    return name
            zfile.close()

            return False

    def mv_icon_to(self, file_name):
        icon_path = self.icon_file_path()
        if icon_path:
            zfile = zipfile.ZipFile(self.ipa_file)

            icon_file = open(file_name, "wb")
            icon_file.write(zfile.read(icon_path))
            icon_file.close()
            zfile.close()
            return True

        return False

    def gen_plist_file(self):
        with open("%s/%s" % (PROJ_PATH, constants.PRODUCT_PLIST), 'r') as f:
            filedata = f.read()
        filedata = filedata.replace('IPA_DOWNPATH', self.downpath)
        filedata = filedata.replace('BUNDLE_ID', self.bundle_identifier())
        filedata = filedata.replace('BUNDLE_VERSION', self.bundle_version())
        filedata = filedata.replace('PRODUCT_NAME', self.app_name())
        with open(self.plistpath, 'w') as f:
            logging.info(type(filedata))
            f.write(filedata.encode('utf8'))
        return True

    def gen_qricon(self):
        import qrcode
        qr_icon_name = "qr_icon.png"
        path = ""
        if self.type == "dogfood":
            path = ""
        else:
            path = "/" + self.type
        url = "http://" + config.DF_DOMAIN + path + "/i/" + self.bundle_identifier()
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        qr_icon_path = self.ipa_path + "/" + qr_icon_name
        qr.make_image().save(qr_icon_path)
        return True

    def extract_icon(self):
        local_icon_file = self.ipa_path + "/icon.png"
        self.mv_icon_to(local_icon_file)
        r = updatePNG(local_icon_file)
        return r

    def upload_ipa(self):
        ret = dict()
        app_info = dict()

        # get icon
        r = self.extract_icon()
        if r is False:
            ret["msg"] = "ERROR: GENERATE ICON FAIL!"

        # generate qrcode icon
        r = self.gen_qricon()
        if r is False:
            ret["msg"] = "ERROR: GENERATE QR CODE ICON FAIL!"

        # generate product plist
        r_plist = self.gen_plist_file()
        if r_plist is not True:
            ret["msg"] = "ERROR: GENERATE PLIST FAIL!"
            return ret

        app_info['type'] = self.type
        app_info['appName'] = self.app_name()
        app_info['bundleID'] = self.bundle_identifier()
        app_info['bundleShortVersion'] = self.bundle_short_version()
        app_info['bundleVersion'] = self.bundle_version()
        app_info['downpath'] = self.downpath
        app_info['icon_path'] = "http://%s%s/icon.png" % \
            (config.DF_DOMAIN, self.ipa_path)
        app_info['md5'] = self.ipa_md5
        app_info['plistpath'] = self.plistpath
        app_info['icon_path'] = "http://%s%s/icon.png" % \
            (config.DF_DOMAIN, self.ipa_path)
        app_info['qr_icon_path'] = "http://%s%s/qr_icon.png" % \
            (config.DF_DOMAIN, self.ipa_path)
        app_info['timestamp'] = self.timestamp
        app_info['uploadTime'] = self.uploadTime

        self.coll.insert_one(app_info)
        ret["msg"] = "success"
        return ret
