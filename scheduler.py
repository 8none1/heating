#!/usr/bin/python
#
### Things to think about :

import time
import datetime
import MySQLdb
import urllib2

debug=False

week_day = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
weekend   = ['Saturday', 'Sunday']

set_base_url = "http://hotpi/set"

db = MySQLdb.connect(host='xxx', user='xxx', passwd='xxx', db='xxx')
cursor = db.cursor()

def log(message):
	if debug:
		print message


def floor_time(dt):
	"Returns a datetime which is floored to the previous 15 minute boundary less one second"
	dt = (dt - datetime.timedelta(minutes=dt.minute % 15, seconds=dt.second, microseconds=dt.microsecond))
	dt = (dt - datetime.timedelta(seconds=1))
	return dt

def day_of_week(dt):
	"Returns the day name from a datetime"
	dt = dt.timetuple()
	dt = time.strftime("%A", dt)
	return dt

def next_boundary(dt):
	"Returns the next 15 minute boundary as a datetime"
	dt = (dt - datetime.timedelta(minutes=dt.minute % 15, seconds=dt.second, microseconds=dt.microsecond))
	dt = (dt + datetime.timedelta(minutes=15))
	return dt

def day_check(day):
	if day != "weekends" and day != "weekdays":
	  today = day_of_week(datetime.datetime.now())
	  if day == today: return True
	elif day == "weekdays":
		today = day_of_week(datetime.datetime.now())
		if today in week_day: 
                  return True
	elif day == "weekends":
		today = day_of_week(datetime.datetime.now())
		if today in weekend: return True
	else:
		log("Day check failed to match")
		return False

def rest_call(function, state, duration=60):
	url = set_base_url+"/"+function+"/"
	if state == 1: url +="on"
        else: url+="off"
	if state:
	  url+="/"+str(duration)
	log(url)
	req = urllib2.Request(url,"")
	resp = urllib2.urlopen(req)
	return resp.read()

def get_schedule():
	now = datetime.datetime.now()
	start = floor_time(now)
	end = next_boundary(now)
	a = cursor.execute("""SELECT * FROM schedule WHERE time > %s AND time < %s AND active=1""", (start, end))
	#a = cursor.execute("""SELECT * FROM schedule""")
	if a < 1:
		return False
	else:
		for row in cursor.fetchall():
			log(row)
			day = row[1]
			start_time = (datetime.datetime.min + row[2]).time()
			action = row[3]
			function = row[4]
			duration = row[5]
			if day_check(day):
				if action == 1:
					if function == "ch":
						log("I would now call the CH ON API")
						log("With a duration of "+str(duration))
						rest_call("ch", True, duration)
					if function == "hw":
						log("I would now call the HW ON API")
						log("with a duration of "+str(duration))
						rest_call("hw", True, duration)
				if action == 0:
					if function == "ch":
						log("CH OFF")
						rest_call("ch", False)
					if function == "hw":
						rest_call("ch", False)
						log("HW OFF")

	

def main():
	# Query the datebase for events which happen in the next 15 minutes
	# (later: Query the special events database as well)
	# Check they should happen today
	# Do them at the right time
	# Done
	#
	# Question:  How to handle environmental feedback.  i.e. it's very cold outside, switch on heating earlier?
	## Don't know.  Worry about this later.
	result = get_schedule()
	if result == False:
		log("Nothing to do")
		return False
        else: return True




if __name__ == "__main__":
  main()

