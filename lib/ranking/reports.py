#!/usr/bin/python

"""
Quick and durty code generating reports based on the information found in the database. 

"""

import os 
import sys
import ConfigParser
config = ConfigParser.RawConfigParser()
config.optionxform = str
config.read("../etc/bgp-ranking.conf")
root_dir = config.get('directories','root')

import datetime
import redis

global_db_slave = redis.Redis(port = int(config.get('redis','port_slave_1')), db=config.get('redis','global'))
history_db = redis.Redis(db=config.get('redis','history'))
history_db_slave = redis.Redis(port = int(config.get('redis','port_slave_1')), db=config.get('redis','history'))

class Reports():
    separator = config.get('input_keys','separator')
    
    def display_graphs_yesterday(self):
        """
        Until the ranking of the current day being computed, there is nothing to display...
        """
        hours = sorted(config.get('routing','update_hours').split())
        first_hour = hours[0]
        timestamp = history_db.get(config.get('ranking','latest_ranking'))
        if timestamp is not None:
            timestamp = timestamp.split()
            today = datetime.date.today()
            if int(timestamp[1]) == int(first_hour) or timestamp[0] != today.strftime("%Y%m%d"):
                return True
        return False
    
    def __init__(self, date, ip_version = 4):
        if self.display_graphs_yesterday():
            date = date - datetime.timedelta(1)
        self.date = date.isoformat()
        self.sources = global_db_slave.smembers('{date}{sep}{key}'.format(date = self.date, \
                            sep = self.separator, key = config.get('input_keys','index_sources')))
        if ip_version == 4:
            self.ip_key = config.get('input_keys','rankv4')
        elif ip_version == 6:
            self.ip_key = config.get('input_keys','rankv6')
        self.impacts = {}
        items = config.items('modules_to_parse')
        for item in items:
            self.impacts[item[0]] = float(item[1])
    
    def build_reports(self):
        self.global_report()
        # FIXME pipeline ? 
        for source in self.sources:
            histo_key = '{histo_key}{sep}{ip_key}'.format(histo_key = source, sep = self.separator, ip_key = self.ip_key)
            # drop the old stuff
            history_db.delete(histo_key)
            self.source_report(source)
    
    def global_report(self):
        histo_key = '{histo_key}{sep}{ip_key}'.format(histo_key = config.get('input_keys','histo_global'), \
                        sep = self.separator, ip_key = self.ip_key)
        # drop the old stuff
        history_db.delete(histo_key)
        for source in self.sources:
            self.source_report(source, config.get('input_keys','histo_global'))

    def source_report(self, source, zset_key = None):
        if zset_key is None:
            zset_key = source
        histo_key = '{histo_key}{sep}{ip_key}'.format(histo_key = zset_key, sep = self.separator, ip_key = self.ip_key)
        asns = global_db_slave.smembers('{date}{sep}{source}{sep}{key}'.format(date = self.date, sep = self.separator, \
                                    source = source, key = config.get('input_keys','index_asns')))
        # FIXME pipeline
        for asn in asns:
            if asn != config.get('modules_global','default_asn'):
                rank = self.get_daily_rank(asn, source)
                if rank is not None:
                    history_db.zincrby(histo_key, asn, float(rank) * self.impacts[str(source)])
    
    def format_report(self, source = None, limit = 50):
        if source is None:
            source = config.get('input_keys','histo_global')
        histo_key = '{histo_key}{sep}{ip_key}'.format(histo_key = source, sep = self.separator, ip_key = self.ip_key)
        return history_db.zrevrange(histo_key, 0, limit, True)
    
    #FIXME pipeline the function ? 
    def get_daily_rank(self, asn, source = None, date = None):
        if source is None:
            source = config.get('input_keys','histo_global')
        if date is None:
            date = self.date
        return history_db_slave.get('{asn}{sep}{date}{sep}{source}{sep}{ip_key}'.format(sep = self.separator, \
                                        asn = asn, date = date, source = source, ip_key = self.ip_key))

    def prepare_graphe_js(self, asn, first_date, last_date, sources = None):
        dates = []
        current = first_date
        while current <= last_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += datetime.timedelta(days=1)

        pipeline = global_db_slave.pipeline()
        for date in dates:
            pipeline.smembers('{date}{sep}{key}'.format(date = date, sep = self.separator, \
                                key = config.get('input_keys','index_sources')))
        lists_sources = pipeline.execute()
        to_return_sources = set(()).union(*lists_sources)

        if sources is None:
            sources = to_return_sources
        else:
            sources = [sources]

        keys = {}
        ranks = {}
        #FIXME pipeline
        for source in sources:
            keys[source] = []
            for date in dates:
                keys[source].append('{asn}{sep}{date}{sep}{source}{sep}{v4}'.format(sep = self.separator, asn = asn, \
                            date = date, source = source, v4 = config.get('input_keys','rankv4')))
            ranks[source] = history_db_slave.mget(keys[source])

        ranks_by_days = {}
        for source in sources:
            i = 0 
            for rank in ranks[source]:
                if rank is not None:
                    asn_day = dates[i]
                    if ranks_by_days.get(asn_day, None) is None:
                        ranks_by_days[asn_day] = float(rank)
                    else:
                        ranks_by_days[asn_day] += float(rank)
                i += 1 
        for ranks in ranks_by_days:
            ranks_by_days[ranks] += 1 
        return ranks_by_days, to_return_sources
        
    def get_asn_descs(self, asn, sources = None):
        if sources is None:
            sources = self.sources
        else:
            sources = [sources]
        asn_timestamps = global_db_slave.smembers(asn)
        asn_descs_to_print = []
        #FIXME pipeline
        for asn_timestamp in asn_timestamps:
            asn_timestamp_key = '{asn}{sep}{timestamp}{sep}'.format(asn = asn, sep = self.separator, timestamp = asn_timestamp)
            nb_of_ips = 0 
            for source in sources:
                nb_of_ips += global_db_slave.scard('{asn_timestamp_key}{date}{sep}{source}'.format(sep = self.separator, \
                                                asn_timestamp_key = asn_timestamp_key, date = self.date, source=source))
            if nb_of_ips > 0:
                owner = global_db_slave.get('{asn_timestamp_key}{owner}'.format(asn_timestamp_key = asn_timestamp_key, \
                                                owner = config.get('input_keys','owner')))
                ip_block = global_db_slave.get('{asn_timestamp_key}{ip_block}'.format(asn_timestamp_key = asn_timestamp_key, \
                                                ip_block = config.get('input_keys','ips_block')))
                asn_descs_to_print.append([asn, asn_timestamp, owner, ip_block, nb_of_ips])
        return asn_descs_to_print


    def get_ips_descs(self, asn, asn_timestamp, sources = None):
        if sources is None:
            sources = self.sources
        else:
            sources = [sources]
        key_list_tstamp = config.get('input_keys','list_tstamp')
        key_infection = config.get('input_keys','infection')
        key_raw = config.get('input_keys','raw')
        key_whois = config.get('input_keys','whois')

        ip_descs_to_print = []
        asn_timestamp_key = '{asn}{sep}{timestamp}{sep}'.format(asn = asn, sep = self.separator, timestamp = asn_timestamp)
        # FIXME pipeline
        for source in sources:
            ips = global_db_slave.smembers('{asn_timestamp_key}{date}{sep}{source}'.format(sep = self.separator, \
                                        asn_timestamp_key = asn_timestamp_key, date = self.date, source=source))
            for ip_details in ips:
                ip, timestamp = ip_details.split(self.separator)
                infection = global_db_slave.get('{ip}{key}'.format(ip = ip_details, key = key_infection))
                raw_informations = global_db_slave.get('{ip}{key}'.format(ip = ip_details, key = key_raw))
                whois = global_db_slave.get('{ip}{key}'.format(ip = ip_details, key = key_whois))
                ip_descs_to_print.append([timestamp, ip, source, infection, raw_informations, whois])
        return ip_descs_to_print
