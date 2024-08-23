#!/usr/bin/env python3
import sys, time

ib = sys.argv[1]
ib_date = ib.split("_")[-1]
week_day = time.strftime("%a", time.strptime(ib_date, "%Y-%m-%d-%H%M")).lower()
day_hour = time.strftime("%H", time.strptime(ib_date, "%Y-%m-%d-%H%M"))
ib_queue = ".".join(ib.split("_X_")[0].split("_")[1:])
print("%s/%s-%s-%s/%s" % (week_day, ib_queue, week_day, day_hour, ib))
