# -*- coding: utf-8 -*-
import re
import os
import datetime 

from modules.abstract_module import AbstractModule


class DshieldTopIPs(AbstractModule):
    # Dshield doesn't give a date for his TopIPs list. So we assume that 
    # the list is updated every days
    date = datetime.date.today()
    directory = 'dshield/topips/'
    
    def __init__(self, raw_dir):
        AbstractModule.__init__(self)
        self.directory = os.path.join(raw_dir, self.directory)
 
    def parse(self):
        """ Parse the list
        """
        self.ips = []
        for file in self.files:
            daily = open(file)
            for line in daily:
                ip = re.findall('((?:\d{1,3}\.){3}\d{1,3})[\s].*',line)
                if len(ip) == 0:
                    continue
                entry = self.prepare_entry(ip = ip[0], source = self.__class__.__name__, timestamp = self.date)
                self.put_entry(entry)
            daily.close()
            self.move_file(file)
