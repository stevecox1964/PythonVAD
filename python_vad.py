'''

#--- Steve Cox --- 1/10/19
# Copyright (c) Stef van der Struijk
# License: GNU Lesser General Public License

# Modified code to play sound from buffer recording
# Added code to wait till sound is finished play so no echo occurs

# Modification of:
# https://github.com/wiseman/py-webrtcvad (MIT Copyright (c) 2016 John Wiseman)
# https://github.com/wangshub/python-vad (MIT Copyright (c) 2017 wangshub)

Requirements:
+ pyaudio - `pip install pyaudio`
+ py-webrtcvad - `pip install webrtcvad`
'''
import webrtcvad
import collections
import sys
import signal
import pyaudio

from array import array
from struct import pack
import wave
import time

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK_DURATION_MS = 30       # supports 10, 20 and 30 (ms)
PADDING_DURATION_MS = 1500   # 1 sec jugement
CHUNK_SIZE = int(RATE * CHUNK_DURATION_MS / 1000)  # chunk to read
CHUNK_BYTES = CHUNK_SIZE * 2  # 16bit = 2 bytes, PCM
NUM_PADDING_CHUNKS = int(PADDING_DURATION_MS / CHUNK_DURATION_MS)

#--- Steve Cox
NUM_WINDOW_CHUNKS = int(240 / CHUNK_DURATION_MS)
#NUM_WINDOW_CHUNKS = int(400 / CHUNK_DURATION_MS)  # 400 ms/ 30ms  ge

NUM_WINDOW_CHUNKS_END = NUM_WINDOW_CHUNKS * 2
START_OFFSET = int(NUM_WINDOW_CHUNKS * CHUNK_DURATION_MS * 0.5 * RATE)

vad = webrtcvad.Vad(1)

#------ Steve Cox
# One time Pygame init

import pygame
pygame.mixer.pre_init(RATE, -16, CHANNELS, 2048) # setup mixer to avoid sound lag
pygame.mixer.init()
pygame.init()

#-------------------------- 

pa = pyaudio.PyAudio()
stream = pa.open(format=FORMAT,
                 channels=CHANNELS,
                 rate=RATE,
                 input=True,
                 start=False,
                 # input_device_index=2,
                 frames_per_buffer=CHUNK_SIZE)


got_a_sentence = False

def normalize(snd_data):
    "Average the volume out"
    MAXIMUM = 32767  # 16384
    times = float(MAXIMUM) / max(abs(i) for i in snd_data)
    r = array('h')
    for i in snd_data:
        r.append(int(i * times))
    return r


while True:
    ring_buffer = collections.deque(maxlen=NUM_PADDING_CHUNKS)
    triggered = False
    voiced_frames = []
    ring_buffer_flags = [0] * NUM_WINDOW_CHUNKS
    ring_buffer_index = 0

    ring_buffer_flags_end = [0] * NUM_WINDOW_CHUNKS_END
    ring_buffer_index_end = 0
    buffer_in = ''
    # WangS
    raw_data = array('h')
    index = 0
    start_point = 0
    StartTime = time.time()
    print("* recording: ")
    stream.start_stream()

    while not got_a_sentence:
        chunk = stream.read(CHUNK_SIZE)
        # add WangS
        raw_data.extend(array('h', chunk))
        index += CHUNK_SIZE
        TimeUse = time.time() - StartTime

        active = vad.is_speech(chunk, RATE)

        sys.stdout.write('1' if active else '_')
        ring_buffer_flags[ring_buffer_index] = 1 if active else 0
        ring_buffer_index += 1
        ring_buffer_index %= NUM_WINDOW_CHUNKS

        ring_buffer_flags_end[ring_buffer_index_end] = 1 if active else 0
        ring_buffer_index_end += 1
        ring_buffer_index_end %= NUM_WINDOW_CHUNKS_END

        # start point detection
        if not triggered:
            ring_buffer.append(chunk)
            num_voiced = sum(ring_buffer_flags)
            if num_voiced > 0.8 * NUM_WINDOW_CHUNKS:
                sys.stdout.write(' Open ')
                triggered = True
                start_point = index - CHUNK_SIZE * 20  # start point
                ring_buffer.clear()
        # end point detection
        else:
            ring_buffer.append(chunk)
            num_unvoiced = NUM_WINDOW_CHUNKS_END - sum(ring_buffer_flags_end)
            
            if num_unvoiced > 0.90 * NUM_WINDOW_CHUNKS_END or TimeUse > 10:
                sys.stdout.write(' Close ')
                triggered = False
                got_a_sentence = True

        sys.stdout.flush()

    sys.stdout.write('\n')
    
    stream.stop_stream()
    print("* done recording")
    got_a_sentence = False

    # write to file
    raw_data.reverse()
    for index in range(start_point):
        raw_data.pop()
        
    raw_data.reverse()
    raw_data = normalize(raw_data)
    
    #--- Steve Cox
    #--- the wav has a header, we need to strip it off before playing
    wav_data = raw_data[44:len(raw_data)] 
    sound = pygame.mixer.Sound(buffer=wav_data)
    sound.play()
    #--- Wait for the sound to finish playing or we get an echo
    while pygame.mixer.get_busy():
        pass
    
    #data = np.zeros((10, 10), dtype="uint8")
    #zmqWave.sendPlayEvent('zzzz',data)
    

stream.close()
