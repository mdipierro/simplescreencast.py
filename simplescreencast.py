#!/usr/bin/python
# -*- coding: utf-8 -*-
# Author: Massimo Di Pierro
# License: GPL - copyright 2016
import os
import sys
import glob
import time
import shutil
import argparse
import requests
import urlparse
import subprocess
import multiprocessing
import pyscreenshot as ImageGrab
import threading
import numpy as np
import cv2
import pyaudio
import wave
import PIL
import SimpleHTTPServer
import SocketServer
from PIL import Image

def rm(paths):
    """portable remove files"""
    for path in paths.split():
        if not path.startswith('.') and not sys.argv[0].endswith(path):
            for name in glob.glob(path):
                if os.path.isfile(name):
                    os.unlink(name)
                elif os.path.isdir(name):
                    shutil.rmtree(name)

def retry_upload(destination, filename):
    """try post file and then retry"""
    for k in range(8):
        retry = 10 # seconds
        try:
            print 'Uploading video to %s ...' % destination
            stream = open(filename, 'rb')                
            requests.post(destination, stream, timeout=10)
            break
        except Exception, e:
            print 'Failed (%s)! Retrying in %s seconds' % (e, pause)
            time.sleep(pause)
            pause *= 2
 
def pic_in_pic(im, mark, position):
    """adds a pic_in_pic to an image"""
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    layer = Image.new('RGBA', im.size, (0,0,0,0))
    layer.paste(mark, position)
    return Image.composite(layer, im, layer)

def process_video(lock, folder, frame_rate, ffmpeg, concat=False, 
                  destination=None, intro=None, outro=None):
    lock.acquire()
    args = (lock, folder, frame_rate, ffmpeg, concat, destination, intro, outro)
    p = multiprocessing.Process(target=process_ffmpeg, args=args)
    p.daemon = True
    p.start()

def shell(command):
    process = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True)
    return process.communicate()[0] #display stdout
 
def process_ffmpeg(lock, folder, frame_rate, ffmpeg='ffmpeg', concat=False, destination=None,
                   intro=None, outro=None):
    dir = os.getcwd()
    os.chdir(folder)    
    if os.path.exists('frame0001.jpg'): # because there must be two frames or ignore
        shell('%s -framerate %s -start_number 0 -i frame%%04d.jpg -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -y video.mp4' % (ffmpeg, frame_rate))
        shell('%s -i video.mp4 -i audio.wav -c:v copy -c:a aac -strict experimental -y output.mp4' % ffmpeg)
        rm('frame*.jpg audio.wav video.mp4')
    os.chdir(dir)
    if concat:
        print 'Generating video (output.mp4) ...'
        rm('framelist.txt')
        filenames = sorted(glob.glob('frames/frames*/output.mp4'))        
        if intro: filenames.insert(0,intro)
        if outro: filenames.append(outro)
        open('framelist.txt','wb').write(''.join("file '%s'\n" % name for name in filenames))
        shell('%s -f concat -i framelist.txt -c copy -y output.mp4' % ffmpeg)
        rm('frames framelist.txt')
        if destination:
            if '://' in destination:
                retry_upload(destination, 'output.mp4')
            else:
                print 'Copying video to %s ...' % destination
                os.system('mv output.mp4 %s' % destination) 
        print 'Done!'        
    lock.release() 

class AudioCapture(threading.Thread):
 
    def __init__(self, chunk=1024, format=pyaudio.paInt16, channels=2, rate=44100):
        threading.Thread.__init__(self)
        self.chunk = chunk 
        self.format = format
        self.channels = channels
        self.rate = rate
        self.frames = []
        self.record = True
        self.looping = True
 
    def run(self):
        p = pyaudio.PyAudio()
        self.p = p
        stream = p.open(format=self.format,
                        channels=self.channels,
                        rate=self.rate,
                        input=True,
                        frames_per_buffer=self.chunk)
        while self.looping:
            data = stream.read(self.chunk)
            if self.record:
                self.frames.append(data)
 
        stream.stop_stream()
        stream.close()
        p.terminate()
         
    def resume(self):
        self.record = True
 
    def pause(self):
        self.record = False
 
    def quit(self):
        # call this before join
        self.looping = False
        return self
     
    def save(self, filename):
        frames, self.frames = self.frames, []
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(frames))
        wf.close()
 
class ScreenCapure(threading.Thread):
 
    def __init__(self, size=(800,600)):
        threading.Thread.__init__(self)
        self.image = None
        self.size = size
        self.record = True
        self.looping = True
 
    def run(self):
        while self.looping:
            try:
                image = ImageGrab.grab()
                if self.record:
                    image.thumbnail(self.size, PIL.Image.ANTIALIAS)
                    self.image = image
            except:
                time.sleep(0.01)

    def resume(self):
        self.record = True
 
    def pause(self):
        self.record = False
 
    def quit(self):
        # call this before join
        self.looping = False
        return self
 
class CameraCapture(threading.Thread):
 
    def __init__(self, size=(200,150), interval=0.10):
        threading.Thread.__init__(self)
        self.camera = cv2.VideoCapture(0)
        self.interval = interval
        self.size = size
        self.image = None
        self.record = True
        self.looping = True       
 
    def run(self):
        rval = True
        while self.camera.isOpened() and rval and self.looping:
            # capture camera
            rval, frame = self.camera.read()
            if rval and self.record:
                image = Image.fromarray(frame)
                image.thumbnail(self.size, PIL.Image.ANTIALIAS)
                self.image = image
            time.sleep(self.interval)
 
    def resume(self):
        self.record = True
 
    def pause(self):
        self.record = False
 
    def quit(self):
        # call this before join
        self.looping = False        
        self.camera.release()
        return self
 
class MainCapture(object):
    def __init__(self, frame_rate=5, images_folder=100, destination=None,
                 screen_size=(800,600), camera_size=(200,150), ffmpeg='ffmpeg',
                 intro=None, outro=None):
        self.duration = 0
        self.frame_rate = frame_rate
        self.images_folder = images_folder
        self.destination = destination
        self.screen_size = screen_size
        self.camera_size = camera_size
        self.ffmpeg = ffmpeg
        self.intro = intro
        self.outro = outro
        self.paused_time = 0
        self.paused = False

    def capture(self, duration):
        if not duration:
            return
        self.duration = duration
        self.screen = screen = ScreenCapure(size=self.screen_size)    
        self.camera = camera = CameraCapture(size=self.camera_size)
        self.audio = audio = AudioCapture()
        screen.start()
        camera.start()
        audio.start()
        k, t0, dt = 0, time.time(), 0   
        rm('frame*.jpg audio*.wav video.mp4, output.mp4')
        lock = multiprocessing.Lock()
        try:
            while dt<self.duration:
                if self.paused:
                    time.sleep(0.01)
                    continue
                t1 = time.time()
                image1 = screen.image
                image2 = camera.image
                if image1 and image2:
                    if image1.size[0] < image2.size[0]:
                        image1, image2 = image2, image1
                    (w1,h1), (w2,h2) = image1.size, image2.size
                    if w2 < 100:
                        composite = image1
                    else:
                        composite = pic_in_pic(image1, image2, (w1-w2-20, h1-h2-20))
                    dt = time.time() - t0 - self.paused_time
                    if k > 0 and k % self.images_folder == 0:
                        audio.save(os.path.join(folder, 'audio.wav'))
                        process_video(lock, folder, self.frame_rate, self.ffmpeg)
                    for i in range(k,int(dt*self.frame_rate)+1):
                        folder = os.path.join('frames/frames%.5i' % (i/self.images_folder))
                        framename = 'frame%.4i.jpg' % (i % self.images_folder)
                        filename = os.path.join(folder,framename)
                        print '%s (%.2f secs)' % (filename, t1-t0)
                        if not os.path.exists(folder):
                            os.makedirs(folder)
                        composite.save(filename)
                    k = i+1
                time.sleep(max(0,1.0/self.frame_rate - (time.time()-t1)))    
        except KeyboardInterrupt:
            print 'Stopping ...'
        except:
            import traceback
            print traceback.format_exc()
        finally:        
            if not os.path.exists(os.path.join(folder, 'audio.wav')):
                audio.save(os.path.join(folder, 'audio.wav'))
            process_video(lock, folder, self.frame_rate, self.ffmpeg, concat=True, 
                          destination=self.destination, intro=self.intro, outro=self.outro)
            lock.acquire()
            for thread in [screen, camera, audio]:
                thread.quit().join()
            lock.release()
    
    def pause(self):
        """can be exposed, pauses the recording"""
        self.paused = True
        self.audio.pause()
        self.start_paused = time.time()
        
    def resume(self):
        """can be exposed, resumes the recording"""
        self.paused_time += (time.time() - self.start_paused)
        self.audio.resume()
        self.paused = False

    def start(self, duration):
        self.duration = duration

    def stop(self):
        """can be exposed, stops the recording for good and makes the output"""
        self.duration = 0

    def loop_and_wait_for_server(self):
        """ loops over multiple videos waiting for instructions """
        while True:
            if self.duration:
                self.capture(self.duration)
            time.sleep(1)

class CommandServer(threading.Thread):
    """
    if started with --server 127.0.0.1:8000:{secret}

    curl "http://127.0.0.1:8008/status?secret={secret}
    curl "http://127.0.0.1:8008/start?secret={secret}&duration=100"
    curl "http://127.0.0.1:8008/pause?secret={secret}&duration=100"
    curl "http://127.0.0.1:8008/resume?secret={secret}"
    curl "http://127.0.0.1:8008/set?secret={secret}&destination=/tmp/output.mp4"
    curl "http://127.0.0.1:8008/stop?secret={secret}"
    curl "http://127.0.0.1:8008/getmovie?secret={secret}"
    """
    def __init__(self, capturer, ip, port, secret):
        self.capturer = capturer
        self.ip = ip
        self.port = port
        self.secret = secret
        self.status = 'stopped'
        threading.Thread.__init__(self)
    def run(self):
        class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
            def do_GET(this):
                path = this.path.split('?')[0]
                vars = urlparse.parse_qs(urlparse.urlparse(this.path).query)
                if vars.get('secret')[0] == self.secret:
                    if path == '/start' and self.status == 'stopped': 
                        print int(vars.get('duration',[0])[0])
                        self.capturer.start(int(vars.get('duration',[0])[0]))
                        self.status = 'started'
                    elif path == '/set':
                        self.capturer.destination = vars.get('destination',[None])[0]
                    elif path == '/pause': 
                        self.capturer.pause()
                        self.status = 'paused'
                    elif path == '/resume' and self.status == 'paused': 
                        self.capturer.resume()
                        self.sttaus = 'started'
                    elif path == '/stop': 
                        self.capturer.stop()      
                        self.status = 'stopped'
                    elif path == '/getmovie' and os.path.exists('output.mp4'):
                         this.send_response(200)
                         this.end_headers()
                         shutil.copyfileobj(open('output.mp4'), this.wfile)
                this.send_response(200)
                this.end_headers()
                this.wfile.write(self.status)          
        print 'Starting server on %s:%s ...' % (self.ip, self.port)
        server = SocketServer.TCPServer((self.ip, self.port), Handler)
        server.serve_forever()

def main():
    parser = argparse.ArgumentParser(description='Simple Screecasting Tool')
    parser.add_argument('--duration', type=int, default=3600,
                        help='screencast duration in seconds')
    parser.add_argument('--frame_rate', type=int, default=5,
                        help='screen shots per second')
    parser.add_argument('--screen_size', type=str, default='800x600',
                        help='desired screen recording size')
    parser.add_argument('--camera_size', type=str, default='200x150',
                        help='desired camera recording size (pic in pic)')
    parser.add_argument('--images_folder', type=int, default=100,
                        help='number of temp images per folder')
    parser.add_argument('--destination', type=str, default=None,
                        help='optional upload url or folder/file where to move/rename video file')
    parser.add_argument('--ffmpeg', type=str, default='ffmpeg',
                        help='full path to ffmpeg')
    parser.add_argument('--delay', type=int, default=5,
                        help='seconds delay before start')
    parser.add_argument('--server', type=str, default=None,
                        help='ip:port:secret for internal server to take commands')
    parser.add_argument('--intro', type=str, default=None,
                        help='mp4 video to prepend to screencast')
    parser.add_argument('--outro', type=str, default=None,
                        help='mp4 video to append to screencast')
    args = parser.parse_args()

    if os.system('ffmpeg')<=0:
        print "Sorry, cannot find ffmpeg (try --ffmpeg='path/to/ffpmeg')"
        sys.exit(-1)

    def parsesize(size): return map(int,size.split('x'))

    while args.delay:
        print 'waiting...',args.delay
        time.sleep(1)
        args.delay -= 1

    capturer = MainCapture(frame_rate=args.frame_rate, 
                           images_folder=args.images_folder, 
                           destination=args.destination,
                           screen_size=parsesize(args.screen_size), 
                           camera_size=parsesize(args.camera_size),
                           ffmpeg=args.ffmpeg,
                           intro=args.intro,
                           outro=args.outro)

    if args.server:
        ip, port, secret = args.server.split(':')
        thread = CommandServer(capturer, ip, int(port), secret)
        thread.start()        
        capturer.loop_and_wait_for_server()
        thread.join()
    else:
        capturer.capture(duration=args.duration)
              
    

if __name__ == '__main__':
    main()
