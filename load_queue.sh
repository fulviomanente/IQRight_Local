#!/bin/sh
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"break1\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"123\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"break2\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"1234\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"break3\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"1235\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"break4\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"1236\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"break5\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"1237\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"break6\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"1238\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"command\":\"break\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break 1\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"1239\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break 2\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12310\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break 3\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12311\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break 4\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12312\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"command\":\"break\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break2 1\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12313\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break2 2\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12314\"}"
sleep 1
mosquitto_pub -d -t Class40 -u IQRight -P 123456 -m "{\"name\":\"After break2 3\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12315\"}"
sleep 1
mosquitto_pub -d -t Class40 -u IQRight -P 123456 -m "{\"name\":\"After break2 4\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12316\"}"
sleep 1
mosquitto_pub -d -t Class40 -u IQRight -P 123456 -m "{\"command\":\"break\"}"
sleep 1
mosquitto_pub -d -t Class40 -u IQRight -P 123456 -m "{\"name\":\"After break3 1\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12317\"}"
sleep 1
mosquitto_pub -d -t Class40 -u IQRight -P 123456 -m "{\"name\":\"After break3 2\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12318\"}"
sleep 1
mosquitto_pub -d -t Class40 -u IQRight -P 123456 -m "{\"name\":\"After break3 3\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12319\"}"
sleep 1
mosquitto_pub -d -t Class30 -u IQRight -P 123456 -m "{\"name\":\"After break3 4\", \"level1\":\"lalala\",\"level2\":\"lelele\",\"externalNumber\":\"12320\"}"