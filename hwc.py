#!/usr/bin/python

# Make it handle DB Gone Away better
# Make it handle sensors gone away better



import MySQLdb
from time import sleep,time
from Adafruit_BMP085 import BMP085


bmp = BMP085(0x77)
hw_sensors = {"top":"28-00000475123b","mid":"28-000005599656","btm":"28-00000474a676"}
debug = True
db = MySQLdb.connect(host='xxx', user='xxx', passwd='xxx', db='xxx')
cursor = db.cursor()
loops = 15
avg_t=avg_m=avg_b = 0
pres_temp=avg_pres_reading = 0
prev_reading_dict = {}


def log(message):
	if debug:
		print message


def get_temp(device):
	try:
		path="/sys/bus/w1/devices/"
		reading="w1_slave"
		tdevice=path+device+"/"+reading
		tfile=open(tdevice)
		text=tfile.read()
		tfile.close()
		second=text.split("\n")[1]
		tempdata=second.split(" ")[9]
		temperature = float(tempdata[2:])
		try:
			if (prev_reading_dict[device] > (temperature + 20000)) or (prev_reading_dict[device] < (temperature - 20000)):
				log("Impluasible signal detected.  Ignoring.")
				return 0
		except KeyError:
			# Probably need to init the previous readings dict
			# which should happen now...
			pass 
		prev_reading_dict[device] = temperature
		if debug:  log(str(temperature/1000))
		return int(round(temperature/1000))
	except:
		log("Error in get_temp function")
		raise

def log_temp(top,mid,btm):
        cursor.execute("""INSERT INTO readings (top, middle, bottom) VALUES (%s,%s,%s)""",(top,mid,btm))
        db.commit()
	log("DB write done.")
	
def log_pressure(pressure, temperature):
  cursor.execute("""INSERT INTO pressure (pressure, temp) VALUES (%s,%s)""", (pressure,temperature))
  db.commit()
  log("Pressure readings done.")

#1st time round, log temps right away
t_tmp = get_temp(hw_sensors['top'])
m_tmp = get_temp(hw_sensors['mid'])
b_tmp = get_temp(hw_sensors['btm'])
log_temp(t_tmp, m_tmp, b_tmp)


while True:
  try:
	for a in range (loops):
		#start_loop=time()
		log("Loop: "+str(a))
		t_tmp = get_temp(hw_sensors['top'])
		m_tmp = get_temp(hw_sensors['mid'])
		b_tmp = get_temp(hw_sensors['btm'])
		pres = (bmp.readPressure()/100.0)
		log(pres)
                prestmp = bmp.readTemperature()
		log(prestmp)
		avg_t += t_tmp
		avg_m += m_tmp
		avg_b += b_tmp
		avg_pres_reading += pres
		pres_temp += prestmp
		#print "Ran for: "+str((time())-start_loop)
		sleep(60)
	# Should have about 15mins worth of readings now
	avg_t = int(round(avg_t / loops))
	avg_m = int(round(avg_m / loops))
	avg_b = int(round(avg_b / loops))
	avg_pres = int(round(avg_pres_reading / loops))
	avg_p_temp = int(round(pres_temp / loops))
	log_temp(avg_t,avg_m,avg_b)
	log_pressure(avg_pres, avg_p_temp)
	avg_t=avg_m=avg_b=avg_pres=avg_p_temp=avg_pres_reading = 0
  except:
	log("Clearing up")
	db.commit()
	cursor.close()
	db.close()
	raise


