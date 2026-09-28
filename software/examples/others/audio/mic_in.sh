#!/bin/sh

amixer -c $1 cset name='PCM Volume' 180 > /dev/null
amixer -c $1 cset name='Capture Digital Volume' 192 > /dev/null
amixer -c $1 cset name='ADC Data Select' 1 > /dev/null
amixer -c $1 cset  name='Output 1 Playback Volume' 32 > /dev/null

amixer -c $1 cset name='Left Line Mux' 1 > /dev/null
amixer -c $1 cset name='Right Line Mux' 1 > /dev/null

amixer -c $1 cset name='Left PGA Mux' 1 > /dev/null
amixer -c $1 cset name='Right PGA Mux' 1 > /dev/null


amixer -c $1 cset name='Differential Mux' 1  > /dev/null

amixer -c $1 cset name='Headphone Switch' 1   > /dev/null

arecord -Dhw:$1,0 -f S16_LE -r 44100 -d 10 -c 2 /userdata/test.wav

echo "record success, play the test.wav"

aplay -Dhw:$1,0 /userdata/test.wav
