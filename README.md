# simplescreencast

Simplescreencast is a simple (one file) program written in Python that can be used to create a screencast (with picture in picture) and/or to automate the screen capture in classrooms.

Simplescreencast works by taking periodic screenshots, camera shots, and recording the audio. It then assembles them all in a single mp4 video. If both screen and camera sources are selected (default) is produces a video with a picture in picture. If the size of one source is set to zero, only the other is recorded. Once the video is produced, it is automatically uploaded it to your server or moved into a speficied destination folder. Simplescreencast also has the ability to run its own server thus exposing API to control the recording.

Simplescreencast run everywhere (Windows, Mac, Linux) as long as it can find its dependencies. 

Here is one looks like: [Example screencast](https://dl.dropboxusercontent.com/u/18065445/Tmp/simplescreencast.mp4)

Simplescreencast is ideal for creating tutorial videos but also for running multiple concurrent classroom recordings.

Examples of usage

```
# simplest usage:
python simplescreencast.py

# ask for help:
python simplescreencast.py -h

# move video to folder when done, for example to Dropbox
python simplescreencast.py --destination /Users/me/Dropbox/Public

# upload video to a url when done
python simplescreencast.py --destination https://example.com/uploads

# change parameters
python simplescreencast.py --delay 5 --screen_size 800x600 --frame_rate 2

# run it a server for remote control
python simplescreencast.py --server 127.0.0.1:8000:secret
```

## Features overview

- screen recording (1 fps)
- camera recording (5 fps, customizable)
- audio recording (44K bits rate)
- picture in picture (if both screen and camera)
- user defined size
- user defined upload POST of final movie
- can prepend an intro video
- can append a closing video
- delayed start
- web API for controlling start/stop/pause/resume/status
- optimized memory footprint (the resulting video is about 150MB/hr at 800x600 resolution)

## Command line options

```
usage: simplescreencast.py [-h] [--duration DURATION]
                           [--frame_rate FRAME_RATE]
                           [--screen_size SCREEN_SIZE]
                           [--camera_size CAMERA_SIZE]
                           [--images_folder IMAGES_FOLDER]
                           [--destination DESTINATION] [--ffmpeg FFMPEG]
                           [--delay DELAY] [--server SERVER] [--intro INTRO]
                           [--outro OUTRO]

Simple Screecasting Tool

optional arguments:
  -h, --help            show this help message and exit
  --duration DURATION   screencast duration in seconds
  --frame_rate FRAME_RATE
                        screen shots per second
  --screen_size SCREEN_SIZE
                        desired screen recording size
  --camera_size CAMERA_SIZE
                        desired camera recording size (pic in pic)
  --images_folder IMAGES_FOLDER
                        number of temp images per folder
  --destination DESTINATION
                        optional upload url or folder/file where to
                        move/rename video file
  --ffmpeg FFMPEG       full path to ffmpeg
  --delay DELAY         seconds delay before start
  --server SERVER       ip:port:secret for internal server to take commands
  --intro INTRO         mp4 video to prepend to screencast
  --outro OUTRO         mp4 video to append to screencast
```

## Dependencies

Simplescreencast depends on the following modues:

- pyscreencast (for portable ImageGrab)
- pyaudio (for audio recording)
- wave (for audio processing)
- PIL (for image processing)
- cv2 (OpenCV2, for camera capture)
- numpy (also for image processing)
- requests (for file uploads)

It also requires ffmpeg installed on the server. 
You can use ```--ffmpeg={path}``` to specify the locaiton of ffmpeg if not found.

## Intro and outro

You can optionally pass two parameters ```--intro``` and ```--outro``` and they must be paths to mp4 movies. Simplescreencast will prepend the intro to the screencast (opening) and append outro (closing).

## Usage as a server

If started with the option ```--server 127.0.0.1:8000:{secret}``` Example of remote API:

``` 
http://127.0.0.1:8008/status?secret={secret}                                                  
http://127.0.0.1:8008/start?secret={secret}&duration=100                                    
http://127.0.0.1:8008/pause?secret={secret}&duration=100                                     
http://127.0.0.1:8008/resume?secret={secret}                                                 
http://127.0.0.1:8008/set?secret={secret}&destination=/tmp/output.mp4                        
http://127.0.0.1:8008/stop?secret={secret}                                                
http://127.0.0.1:8008/getmovie?secret={secret} 
```

We recommend not using "getmovie" because unreliable, but using "set" destination to 
register an upload URL and let simplescreencast post the movie when done.

Notice the internal web server does not support HTTPS and it is intended to be used from localhost.

## License and credits

Created by Massimo Di Pierro - GPL License - Copyright 2016
