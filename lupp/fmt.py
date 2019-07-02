#!/usr/bin/env python

"""
Formatting for times, dates, distances
"""

import datetime
import time
import json
import re


# Time conversion

def sec_as_hms(seconds):
    """3700 -> 1:01:40"""
    dateandtime = (hms(datetime.datetime(2000, 1, 1, 0, 0, 0) +
                       datetime.timedelta(seconds=seconds)))
    return dateandtime if dateandtime[0] != "0" else dateandtime[1:]


def sec_as_hm(seconds):
    """3700 -> 1:01"""
    dateandtime = (hm(datetime.datetime(2000, 1, 1, 0, 0, 0) +
                      datetime.timedelta(seconds=seconds)))
    return dateandtime if dateandtime[0] != "0" else dateandtime[1:]


def sec_as_ms(seconds):
    """123 -> 2:03"""
    dateandtime = (ms(datetime.datetime(2000, 1, 1, 0, 0, 0) +
                      datetime.timedelta(seconds=seconds)))
    return dateandtime if dateandtime[0] != "0" else dateandtime[1:]


def duration_hms(time_delta):
    """time_delta -> 1:01:40"""
    minutes, s = divmod(time_delta, 60)
    h, minutes = divmod(minutes, 60)
    return "%d:%02d:%02d" % (h, minutes, s)


def duration_hm(time_delta):
    """time_delta -> 1:01"""
    minutes, s = divmod(time_delta, 60)
    h, minutes = divmod(minutes, 60)
    return "%d:%02d" % (h, minutes)


# Date & time conversion

def datetime_from_ymd_hms(a_str):
    """Datetime object from string timestamp format 1970-01-01 00:00:00"""
    return datetime.datetime.strptime(a_str, "%Y-%m-%d %H:%M:%S")


def datetime_from_ymd(a_str):
    """2013-12-11 or 13/12/11 - len 6 or 8 ok"""
    a_str = just_0123456789(a_str)
    if len(a_str) == 6:
        a_datetime = datetime.datetime.strptime(a_str, "%y%m%d")
    elif len(a_str) == 8:
        a_datetime = datetime.datetime.strptime(a_str, "%Y%m%d")
    else:
        raise Exception("date_from_ymd: Invalid date length %s for date %s"
                        % (len(a_str), a_str))
    return a_datetime


def datetime_from_dmy(a_str):
    """03.01.2012 or 11.12.13 - len 6 or 8 ok"""
    a_str = just_0123456789(a_str)
    if len(a_str) == 6:
        a_datetime = datetime.datetime.strptime(a_str, "%d%m%y")
    elif len(a_str) == 8:
        a_datetime = datetime.datetime.strptime(a_str, "%d%m%Y")
    else:
        raise Exception("date_from_ymd: Invalid date length " + a_str)
    return a_datetime


def datetime_from_timestamp(a_sqlite3_timestamp):
    dt = datetime.datetime.fromtimestamp(a_sqlite3_timestamp)
    dt += datetime.timedelta(days=31*365+8)
    return dt


def time_from_hms(a_str):
    """14:15:16, 14.15.16 or 14h15 - len 4 or 6 ok"""
    a_str = just_0123456789(a_str)
    if len(a_str) == 4:
        a_time = datetime.datetime.strptime(a_str, "%H%M").time()
    elif len(a_str) == 6:
        a_time = datetime.datetime.strptime(a_str, "%H%M%S").time()
    else:
        raise Exception("date_from_ymd: Invalid date length " + a_str)
    return a_time


def just_0123456789(a_str):
    """Format string to remove all other chars than digits"""
    return re.compile(r'[^\d]+').sub("", a_str)


def no_0123456789(a_str):  # remove all numbers
    """Remove all digits from string"""
    return re.compile(r'[\d]+').sub("", a_str)


def current_timestamp():
    """String with current time"""
    return time.strftime("%d.%m.%Y %H:%M")


def current_date_yymd():
    """String with current date foramtted as '1970-01-01'"""
    return time.strftime("%Y-%m-%d")


def current_time_hm():
    """String with current time formatted as '59:69'"""
    return time.strftime("%H:%M")


def onedecimal(a_float):
    """Example: '1234,5'"""
    return f"{a_float:.1f}".replace(".", ",")


def i1000(an_int):
    """Example: '1.234.567'"""
    return f"{an_int:,}".replace(",", ".")


def km(km_float):
    """Example: '12,3 km'"""
    return onedecimal(km_float) + " km"


def m(km_float):
    """Example: '12.345 m'"""
    return i1000(int(1000 * km_float + 0.5)) + " m"


def mm2(mm):
    """Leave int values, give floats 2 decimals - for legible SVG"""
    if type(mm) == int:
        return str(mm)
    if type(mm) == float:
        return "{:.2f}".format(mm)
    return str(mm)


def pretty_dict(d):
    """Format python dict and print it"""
    s = json.dumps(d, sort_keys=True, indent=2)
    for r in s.splitlines():
        r = r.replace('{', '')
        r = r.replace('}', '')
        r = r.replace('"', '')
        r = r.replace(',', '')
        if r.strip() != "":
            print(r)


# Date & time formatting

def yymd(a_datetime):
    """ '2012-11-10' """
    return a_datetime.strftime("%Y-%m-%d")


def dmyy(a_datetime):
    """'09.08.2012'"""
    return a_datetime.strftime("%d.%m.%Y")


def ymd6(a_datetime):
    """'121110'"""
    return a_datetime.strftime("%y%m%d")


def hms(a_datetime):
    """'14:53:59'"""
    return a_datetime.strftime("%H:%M:%S")


def hm(a_datetime):
    """'14:53'"""
    return a_datetime.strftime("%H:%M")


def hms6(a_datetime):
    """'145359'"""
    return a_datetime.strftime("%H%M%S")


def ms(a_datetime):
    """'53:59'"""
    return a_datetime.strftime("%M:%S")
