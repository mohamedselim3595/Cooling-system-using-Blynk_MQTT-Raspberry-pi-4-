#!/usr/bin/env python3
import time, ssl
import board
import adafruit_dht
from gpiozero import LED, Buzzer, Motor
from RPLCD.i2c import CharLCD
import config
from paho.mqtt.client import Client, CallbackAPIVersion
from urllib.parse import urlparse

# --- Hardware setup ---
dht_device = adafruit_dht.DHT11(board.D27)

yellow_led = LED(17)      # adjust pins
red_led = LED(22)
buzzer = Buzzer(23)
fan = Motor(forward=24, backward=25)

lcd = CharLCD('PCF8574', 0x27)  # check your I2C addr (0x27 / 0x3F)

# --- Blynk MQTT setup ---
mqtt = Client(CallbackAPIVersion.VERSION2)

def on_connect(mqtt, obj, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected [secure]")
        mqtt.subscribe("downlink/#", qos=0)
    elif reason_code == "Bad user name or password":
        print("Invalid BLYNK_AUTH_TOKEN")
        mqtt.disconnect()
    else:
        raise Exception(f"MQTT connection error: {reason_code}")

def on_message(mqtt, obj, msg):
    payload = msg.payload.decode("utf-8")
    topic = msg.topic
    print(f"Got {topic}, value: {payload}")

mqtt.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
mqtt.on_connect = on_connect
mqtt.on_message = on_message
mqtt.username_pw_set("device", config.BLYNK_AUTH_TOKEN)
mqtt.connect_async(config.BLYNK_MQTT_BROKER, 8883, 45)
mqtt.loop_start()

# --- Main loop ---
while True:
    try:
        temp = dht_device.temperature
        hum = dht_device.humidity

        print(f"Temp: {temp}°C  Humidity: {hum}%")

        # --- Update LCD ---
        lcd.clear()
        lcd.write_string(f"Temp:{temp}C Hum:{hum}%")

        # --- Reset outputs ---
        yellow_led.off()
        red_led.off()
        buzzer.off()
        fan.stop()

        # --- State machine ---
        if temp < 24:
            lcd.cursor_pos = (1, 0)
            lcd.write_string("State 1: Normal")

        elif 24 <= temp <= 25.9:
            yellow_led.on()
            fan.forward()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("State 2: Cooling")

        else:  # temp >= 26
            red_led.on()
            buzzer.on()
            fan.forward()
            lcd.cursor_pos = (1, 0)
            lcd.write_string("State 3: Alert!")

        # --- Publish to Blynk ---
        mqtt.publish("ds/temp", str(int(temp)))     # temperature
        mqtt.publish("ds/Humidity", str(int(hum)))      # humidity
        mqtt.publish("ds/Buzzer", "1" if buzzer.is_active else "0")
        mqtt.publish("ds/Led1", "1" if yellow_led.is_lit else "0")
        mqtt.publish("ds/Led2", "1" if red_led.is_lit else "0")

        time.sleep(2)

    except RuntimeError as e:
        print("Reading error:", e.args[0])
        time.sleep(2)
        continue
    except Exception as e:
        dht_device.exit()
        raise e
