#!/usr/bin/python
# -*- coding: utf-8 -*-
# Inspired by : http://gitorious.org/forban/forban/blobs/master/bin/forbanctl

"""
Start a process for all the modules listed in 'options'
"""

import os 
import sys
import ConfigParser
config = ConfigParser.RawConfigParser()
config.read("../bgp-ranking.conf")
root_dir = config.get('global','root')
sys.path.append(os.path.join(root_dir,config.get('global','lib')))
services_dir = os.path.join(root_dir,config.get('global','services'))

from helpers.initscript import *
import signal

def usage():
    print("start_parse_raw_files.py (start|stop)")
    exit (1)

if len(sys.argv) < 2:
    usage()
service = os.path.join(services_dir, "parse_raw_files")


options = config.get('global','modules_to_parse').split()

if sys.argv[1] == "start":
    for option in options:
        print('Start parsing of ' + option)
        syslog.syslog(syslog.LOG_INFO, 'Start parsing of ' + option)
        proc = service_start_once(servicename = service, param = option, processname = service + option)
elif sys.argv[1] == "stop":
    for option in options:
        print('Stop parsing of ' + option)
        syslog.syslog(syslog.LOG_INFO, 'Stop parsing of ' + option)
        pid = pidof(processname=service + option)
        if pid:
            pid = pid[0]
            try:
                os.kill(int(pid), signal.SIGKILL)
            except OSError, e:
                print(option + " unsuccessfully stopped")
                syslog.syslog(syslog.LOG_ERR, option + " unsuccessfully stopped")
            rmpid(processname=service + option)
        else:
            print('No running parsing processes')
            syslog.syslog(syslog.LOG_INFO, 'No running parsing processes')
else:
    usage()