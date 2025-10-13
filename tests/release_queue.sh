#!/bin/sh
mosquitto_pub -d -t IQSend -u IQRight -P 123456 -m "{\"command\":\"release\"}"
