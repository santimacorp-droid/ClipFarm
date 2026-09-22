#!/bin/bash

# WhisperProcess status check script
# Rapid system status checker

echo "🔍 AutoClip WhisperProcess status check"
echo "=================================="

# CheckWhisperProcesses
echo "📊 WhisperProcess state:"
python scripts/monitor_whisper.py

echo ""
echo "📈 System resource usage:"
echo "CPUUsage rate: $(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')"
echo "Memory usage: $(ps -A -o %mem | awk '{s+=$1} END {print s "%"}')"

echo ""
echo "🛠️ Available commands:"
echo "  Check status: python scripts/monitor_whisper.py"
echo "  Clean duplicates: python scripts/monitor_whisper.py --kill-duplicates"
echo "  Stop system: ./stop_autoclip.sh"
