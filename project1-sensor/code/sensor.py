import smbus
import time
from ctypes import c_short
import Adafruit_DHT
import RPi.GPIO as GPIO
import mysql.connector as mariadb

# XD-83 rain sensor
# ------------------------------------------------------------
GPIO.setmode(GPIO.BCM)

sensor_xd_pin = 17

GPIO.setup(sensor_xd_pin, GPIO.IN)


def read_xd83():
    if GPIO.input(sensor_xd_pin) == 1:
        return 0
    else:
        return 1

# DHT22 temperature and humidity sensor
# ------------------------------------------------------------
sensor_dht = Adafruit_DHT.DHT22
sensor_dht_pin = 4

# BMP180 air pressure sensor
# ------------------------------------------------------------
DEVICE = 0x77
bus = smbus.SMBus(1)


def convertToString(data):
    return str((data[1] + (256 * data[0])) / 1.2)


def getShort(data, index):
    return c_short((data[index] << 8) + data[index + 1]).value


def getUshort(data, index):
    return (data[index] << 8) + data[index + 1]


def readBmp180Id(addr=DEVICE):
    REG_ID = 0xD0
    (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
    return (chip_id, chip_version)


def readBmp180(addr=DEVICE):
    REG_CALIB = 0xAA
    REG_MEAS = 0xF4
    REG_MSB = 0xF6
    REG_LSB = 0xF7
    CRV_TEMP = 0x2E
    CRV_PRES = 0x34
    OVERSAMPLE = 3
    cal = bus.read_i2c_block_data(addr, REG_CALIB, 22)

    AC1 = getShort(cal, 0)
    AC2 = getShort(cal, 2)
    AC3 = getShort(cal, 4)
    AC4 = getUshort(cal, 6)
    AC5 = getUshort(cal, 8)
    AC6 = getUshort(cal, 10)
    B1 = getShort(cal, 12)
    B2 = getShort(cal, 14)
    MB = getShort(cal, 16)
    MC = getShort(cal, 18)
    MD = getShort(cal, 20)

    bus.write_byte_data(addr, REG_MEAS, CRV_TEMP)
    time.sleep(0.005)
    (msb, lsb) = bus.read_i2c_block_data(addr, REG_MSB, 2)
    UT = (msb << 8) + lsb

    bus.write_byte_data(addr, REG_MEAS, CRV_PRES + (OVERSAMPLE << 6))
    time.sleep(0.04)
    (msb, lsb, xsb) = bus.read_i2c_block_data(addr, REG_MSB, 3)
    UP = ((msb << 16) + (lsb << 8) + xsb) >> (8 - OVERSAMPLE)

    X1 = ((UT - AC6) * AC5) >> 15
    X2 = (MC << 11) / (X1 + MD)
    B5 = X1 + X2
    temperature = int(B5 + 8) >> 4

    B6 = B5 - 4000
    B62 = int(B6 * B6) >> 12
    X1 = (B2 * B62) >> 11
    X2 = int(AC2 * B6) >> 11
    X3 = X1 + X2
    B3 = (((AC1 * 4 + X3) << OVERSAMPLE) + 2) >> 2

    X1 = int(AC3 * B6) >> 13
    X2 = (B1 * B62) >> 16
    X3 = ((X1 + X2) + 2) >> 2
    B4 = (AC4 * (X3 + 32768)) >> 15
    B7 = (UP - B3) * (50000 >> OVERSAMPLE)

    P = (B7 * 2) / B4

    X1 = (int(P) >> 8) * (int(P) >> 8)
    X1 = (X1 * 3038) >> 16
    X2 = int(-7357 * P) >> 16
    pressure = int(P + ((X1 + X2 + 3791) >> 4))

    return (temperature / 10.0, pressure / 100.0)


# MySQL
# ------------------------------------------------------------
def set_data(sql, params=None):
    try:
        conn = mariadb.connect(database='weerstation', user='project1-sensor', password='sensorpassword')
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        return False


# reading and processing data
# ------------------------------------------------------------

pressure = readBmp180()[1]
humidity, temperature = Adafruit_DHT.read_retry(sensor_dht, sensor_dht_pin)
rain = read_xd83()
#print("pressure: " + str(pressure))
#print("humidity: " + str(humidity))
#print("temperature: " + str(temperature))
#print("raining: " + str(rain))

sql = "insert into data values" \
      "(DEFAULT, (SELECT SensorID FROM sensor WHERE type = 'temperatuur') , %s)," \
      "(DEFAULT, (SELECT SensorID FROM sensor WHERE type = 'luchtvochtigheid') , %s)," \
      "(DEFAULT, (SELECT SensorID FROM sensor WHERE type = 'luchtdruk') , %s)," \
      "(DEFAULT, (SELECT SensorID FROM sensor WHERE type = 'neerslag') , %s);"

set_data(sql, (temperature, humidity, pressure, rain))
#if set_data(sql, (temperature, humidity, pressure, rain)):
#    print("data submitted successfully")
#else:
#    print("error submitting data into database")
