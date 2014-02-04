#!/usr/bin/python

## Things to do
# MOVE TO SEPERATE CODE: Add temp sensor network to main loop
# MOVE TO SEPERATE CODE: Build scheduler
# MOVE TO SEPERATE CODE: Add pressure sensor & tank sensors



import RPi.GPIO as GPIO
from datetime import datetime, timedelta
import time
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from SocketServer import ThreadingMixIn
import threading
import json

debug=True
GPIO.setmode(GPIO.BCM)

## Input GPIOs
hw_switch = 24
ch_switch = 23
inputs=[hw_switch, ch_switch]

## Output GPIOs
hw_led  = 7
ch_led  = 8
sig_led = 25
psu_relay     = 17
ch_on_relay   = 21
hw_on_relay   = 22
hw_off_relay  = 18
leds =  [hw_led, ch_led, sig_led]
relays = [ch_on_relay, hw_on_relay,hw_off_relay, psu_relay]

## Globals
press_time = {}
release_time = {}
hw_override = False
ch_override = False
psu = False
global hw_off_time
global ch_off_time
hw_off_time = False
ch_off_time = False


## Set up inputs & outputs

for each in inputs:
  GPIO.setup(each,GPIO.IN)
  GPIO.add_event_detect(each, GPIO.FALLING)    

for item in [relays, leds]:
  for each in item:
    GPIO.setup(each, GPIO.OUT, initial=True)

def log(message):
  if debug:  print message

def set_gpio_state(gpio, state):
  if gpio not in relays and gpio not in leds:  return False
  else:
    if gpio in relays or gpio in leds:  GPIO.output(gpio, not state)
    else: GPIO.output(gpio, state)
    return True

def get_gpio_state(gpio):
  if gpio not in relays and gpio not in leds: return False
  else:
    if gpio in relays or gpio in leds:  return not GPIO.input(gpio)
    else: return GPIO.input(gpio)

def get_current_status():
  hw_on_state =  get_gpio_state(hw_on_relay)
  hw_off_state = get_gpio_state(hw_off_relay)
  ch_on_state =  get_gpio_state(ch_on_relay)
  return (hw_on_state,hw_off_state,ch_on_state)

def output_test():
  for outputs in [relays, leds]:
    for each in outputs:
      if each == psu_relay: continue
      set_gpio_state(each, True)
      log("Testing output: "+str(each))
      time.sleep(0.1)
      set_gpio_state(each, False)
      time.sleep(0.1)


## Necessary evil
class HTTPRequestHandler(BaseHTTPRequestHandler):
    sys_version="0.00"
    server_version="PiWarmer HTTP API Server/"
    def send_headers(self,code):
        BaseHTTPRequestHandler.send_response(self, code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
    def send_response(self, code=200, data=''):
        self.send_headers(code)
        if type(data) == dict:
          data = json.dumps(data)
        self.wfile.write(data)

    def do_POST(self):
        request = self.path.split('/')
        response_dict={}
        if request[1] == 'set':
          if request[2] == 'hw':
            if request[3] == 'on':
              try:
                if int(request[4]) < 240:
                  run_length = int(request[4])
                else:
                  run_length = 60
              except:
                run_length = 60
              state = hw_state(True, run_length)
              response_dict['state']=state
              response_dict['offtime']=to_epoch(hw_off_time)
              response_dict['result']=True
              code=200
            elif request[3] == 'off':
              state = hw_state(False)
              response_dict['state']=state
              response_dict['result']=True
              code = 200
            else:
              code=400
              response_dict['result']=False
          elif request[2] == 'ch':
            if request[3] == 'on':
              try:
                if int(request[4]) < 240:
                  run_length = int(request[4])
                else:
                  run_length = 60
              except:
                run_length = 60
              state = ch_state(True,run_length)
              response_dict['state']=state
              response_dict['offtime']=to_epoch(ch_off_time)
              response_dict['result']=True
              code=200
            elif request[3] == 'off':
              state=ch_state(False)
              response_dict['state']=state
              response_dict['result']=True
              code=200
            else:
              code=400
              response_dict['result']=False
          elif request[2] == "psu":
	    if request[3] == "on":
	       state = activate_board(True)
	    if request[3] == "off":
	       state = activate_board(False)
	    response_dict['state']=state
	    response_dict['result']=True
	    code=200            
	  else:
            code=403
            response_dict['result']=False
        else:
          code=403
          response_dict['result']=False
        self.send_response(code,response_dict)
        return

    def do_GET(self):
        # <server>/set/hw/on/[mins]
        # <server>/set/ch/on/[mins]
        # <server>/get/hw
        # <server>/get/ch
        # JSON struct
        # result: <True/False> - was the request actioned?
        # state: <True/False> - what is the state of the thing that was asked for?
        # [offtime: <datetime> - if state = on, what time will it go off?]
        # 
        request = self.path.split('/')
        response_dict = {}
        if request[1] == 'get':
          if request[2] == 'hw':
            state = get_gpio_state(hw_on_relay)
            response_dict['state']=state
            if state:
              global hw_off_time
              response_dict['offtime']=to_epoch(hw_off_time)
            response_dict['result']=True  
            code = 200
          elif request[2] == 'ch':
            state = get_gpio_state(ch_on_relay)
            response_dict['state']=state
            if state:
              global ch_off_time
              response_dict['offtime']=to_epoch(ch_off_time)
            response_dict['result']=True
            code=200
          elif request[2]=="psu":
	    state = get_gpio_state(psu_relay)
            response_dict['state']=state
	    response_dict['result']=True
            code=200
	  else:
              code=400
              response_dict['result']=False
        else:
          code=403
          response_dict['result']=False
        self.send_response(code,response_dict)
        return
 
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  allow_reuse_address = True
 
  def shutdown(self):
    self.socket.close()
    HTTPServer.shutdown(self)
 
class SimpleHttpServer():
    def __init__(self, ip='0.0.0.0', port=80):
        self.server = ThreadedHTTPServer((ip,port), HTTPRequestHandler)
 
    def start(self):
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
 
    def waitForThread(self):
        self.server_thread.join()
 
    def stop(self):
        self.server.shutdown()
        self.waitForThread()


def to_epoch(dt):
  return int(time.mktime(dt.timetuple()))



def rest(psu, start_loop):
  if psu:  nap = 0.3
  else:  nap = 1
  rest_time = (start_loop+nap)-start_loop
  #log("Rest time: "+str(rest_time))
  time.sleep(rest_time)    

def error_flash():
  set_gpio_state(sig_led, False)
  for x in range(10):
    for each in leds:
      set_gpio_state(each, not GPIO.input(each))
    time.sleep(0.15)

def activate_board(state):
    global psu
    for output in [relays,leds]:
      for each in output:
        set_gpio_state(each, False)
    if state == True:
      set_gpio_state(psu_relay, True)
      log("MAIN POWER ON")
      psu=True
      return True
    else:
      global hw_off_time
      global ch_off_time
      hw_off_time = False
      ch_off_time = False
      log("MAIN POWER OFF")
      psu=False
      return False

def schedule():
  global hw_off_time
  global ch_off_time
  now = datetime.now()
  if ch_off_time is not False:
    if now > ch_off_time:
      ch_state(False)
      ch_off_time = False
  if hw_off_time is not False:
    if now > hw_off_time:
      hw_state(False)
      hw_off_time = False

    
def button_press(channel):
  # Assume all presses are activate on falling edge
  # So all GPIOs have pull-up.
  press_time[channel] = time.time()
  a = 0
  while not GPIO.input(channel) and a < 150:
    time.sleep(0.02)
    a+=1
  hold_time = time.time()-press_time[channel]
  if hold_time > 0.006:
    #log("Released! Hold time ("+str(channel)+": " + str(hold_time))
    return (True,hold_time)
  else:
    return (False,-1)

def active(state):
  if state:
    set_gpio_state(sig_led, not get_gpio_state(sig_led))
  else:
    set_gpio_state(sig_led, not get_gpio_state(sig_led))
    set_gpio_state(hw_led, not get_gpio_state(hw_led))
    set_gpio_state(ch_led, not get_gpio_state(ch_led))
  # Do schedule check stuff
  return True


########
# Function  |  HW_OFF |  HW_ON  |  CH_ON
# All off   |   0     |    0    |    0
# HW Only   |   0     |    1    |    0
# CH Only   |   1     |    0    |    1
# All on    |   0     |    1    |    1
########


def hw_state(state,duration=60):
  global hw_off_time
  global psu
  hw_on_state,hw_off_state,ch_on_state=get_current_status()
  #if state == hw_on_state: return False
  if not psu:  return False
  if state:
    if ch_on_state:
      set_gpio_state(hw_off_relay, False)
      set_gpio_state(hw_on_relay, True)
    else:
      set_gpio_state(hw_on_relay, True)
    set_gpio_state(hw_led, True)
    hw_off_time=(datetime.now() + timedelta(minutes=duration))
    log("HW ON")
    return True
  if state == False:
    global hw_off_time
    if ch_on_state:
      set_gpio_state(hw_on_relay, False)
      set_gpio_state(hw_off_relay, True)
    else:
      set_gpio_state(hw_on_relay, False)
    set_gpio_state(hw_led, False)
    hw_off_time = False
    log("HW OFF")
    return False

def ch_state(state,duration=60):
  global psu
  global ch_off_time
  hw_on_state,hw_off_state,ch_on_state=get_current_status()
  #if state == ch_on_state: return False
  if not psu: return False
  if state:
    if hw_on_state == False:
      set_gpio_state(ch_on_relay, True)
      set_gpio_state(hw_off_relay, True)
    if hw_on_state:
      set_gpio_state(ch_on_relay, True)
    set_gpio_state(ch_led, True)
    ch_off_time=(datetime.now() + timedelta(minutes=duration))
    log("CH ON")
    return True
  if state == False:
    global ch_off_time
    if hw_on_state:
      set_gpio_state(ch_on_relay, False)
    if hw_on_state == False:
      set_gpio_state(ch_on_relay, False)
      set_gpio_state(hw_off_relay, False)
    set_gpio_state(ch_led, False)
    ch_off_time = False
    log("CH OFF")
    return False
    


def main():
  try:
    output_test()
    global psu
    global hw_off_time
    global ch_off_time
    psu=False
    log("Running...")
    while True:
      start_loop=time.time()
      if GPIO.event_detected(hw_switch):
        real,ptime = button_press(hw_switch)
        if real and ptime > 1.5:
           # Long press on left button means toggle main power
           psu=activate_board(not get_gpio_state(psu_relay))
        elif real:
          # Toggle HW
          if psu:
            state = hw_state(not get_gpio_state(hw_on_relay))
          else: error_flash()
      elif GPIO.event_detected(ch_switch):
        real,ptime = button_press(ch_switch)
        if real:
          if psu:
            state=ch_state(not get_gpio_state(ch_on_relay))
          else: error_flash()
      else:
        if psu:
          schedule()
        active(psu)
        rest(psu,start_loop)
  finally:
    print "Cleaning up"
    GPIO.cleanup()
    server.stop()


if __name__=="__main__":
  server = SimpleHttpServer()
  server.start()
  main()



