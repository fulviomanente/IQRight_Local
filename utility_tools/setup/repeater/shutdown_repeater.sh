#!/bin/bash
# Daily scheduled shutdown at 6:00 PM

logger "Cron: Repeater daily shutdown initiated at $(date)"
/sbin/shutdown -h now
