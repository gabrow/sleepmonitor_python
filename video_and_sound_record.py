import PySpin
import sys
import datetime
import time
import cv2
import psutil
import pyaudio
import wave


###############################################################################
####################### GLOBAL PARAMETER SETTINGS #############################

##### VIDEO #####
VideoFormat = PySpin.H264Option  #leave it as is to record mp4 format videos

FramerateToSet = 20    #this will change the camera's acquisiton framerate and also the videofile framerate, but should not be more than 30
SecondsToRecord = 20  #change this number according to how long you want your video file to be
PartsToRecord = 1      #in how many parts you want to record the above set time // for example: 180s with 3 parts will be 3pcs of 60s video
VideoBitrate = 1000000  #change this to the wanted bitrate of the video file // 1Mbit should be OK
ScaleUpperLimit = 310.0
ScaleLowerLimit = 290.0

NUM_IMAGES = SecondsToRecord * FramerateToSet
ImageHeight = 480
ImageWidth = 640

##### SOUND #####
chunk = 1024  # Record in chunks of 1024 samples
sample_format = pyaudio.paInt16  # 16 bits per sample
channels = 2
sample_rate = 44100  # Record at 44100 samples per second


###############################################################################
###############################################################################

def acquire_and_save(cam, nodemap):
    try:
        result = True

        #set parameters, scale, fps
        node = PySpin.CEnumerationPtr(nodemap.GetNode('ImageAdjustMode'))
        node.SetIntValue(node.GetEntryByName('Manual').GetValue())

        node = PySpin.CFloatPtr(nodemap.GetNode('ScaleLimitLow'))
        node.SetValue(ScaleLowerLimit)

        node = PySpin.CFloatPtr(nodemap.GetNode('ScaleLimitUpper'))
        node.SetValue(ScaleUpperLimit)

        node = PySpin.CEnumerationPtr(nodemap.GetNode('NoiseReduction'))
        node.SetIntValue(node.GetEntryByName('On').GetValue())

        node = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))
        node.SetValue(FramerateToSet)

        # Set acquisition mode to continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            print('Unable to set acquisition mode to continuous (enum retrieval). Aborting...')
            return False

        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(node_acquisition_mode_continuous):
            print('Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
            return False

        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()

        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        print('Acquisition mode set to continuous...')

        cam.BeginAcquisition()

        print("Acquiring images...")

        print('Frame rate to be set to %d...' % FramerateToSet)
        
        FramesPerCycle = int(NUM_IMAGES/PartsToRecord)
        part = 0

        while part < PartsToRecord:
            part += 1

            #defining parameters of video file
            video_filename = "Video_part" + str(part) + "_{date:%Y-%m-%d_%H:%M:%S}".format(date=datetime.datetime.now()) + ".mp4"
            size = (640, 480)
            vid = cv2.VideoWriter(video_filename,cv2.VideoWriter_fourcc(*'mp4v'), FramerateToSet, size)

            #setting sound file parameters
            audio_filename = "Audio_part" + str(part) + "_{date:%Y-%m-%d_%H:%M:%S}".format(date=datetime.datetime.now()) + ".wav"

            vidaudio_filename = "VideoWithAudio_part" + str(part) + "_{date:%Y-%m-%d_%H:%M:%S}".format(date=datetime.datetime.now()) + ".mp4"

            p = pyaudio.PyAudio()
            stream = p.open(format=sample_format,
                            channels=channels,
                            rate=sample_rate,
                            frames_per_buffer=chunk,
                            input=True)
            print("Starting sound recording")

            sound_frames = []

            #capturing frames from FLIR camera and appending them to video file
            for i in range(FramesPerCycle):
                try:
                    #measure time of frame processing
                    process_start = time.time()

                    image_result = cam.GetNextImage(1000)

                    for j in range(0, int(sample_rate / chunk / FramerateToSet)):
                        sound_data = stream.read(chunk)
                        sound_frames.append(sound_data)

                    if image_result.IsIncomplete():
                        print("Image %d is incomplete. Status: %d" % (i, image_result.GetImageStatus()))

                    else:
                        print("Grabbed image %d of %d for part %d/%d" % (i+1, FramesPerCycle, part, PartsToRecord))

                        #converting grabbed frame's data to correct format
                        image_data = image_result.GetNDArray()
                        image_result.Release()

                        #norming values from ~24000-26000 interval to 0-255 interval
                        image_data = image_data - 23900
                        image_data = cv2.convertScaleAbs(image_data, alpha=(255.0/2200.0))

                        #converting color so cv2.VideoWriter can process it
                        image_data = cv2.cvtColor(image_data, cv2.COLOR_GRAY2BGR)

                        cv2.imshow("View",image_data)
                        cv2.waitKey(1)

                        #writing single image to video file
                        vid.write(image_data)

                        print("Appended image %d of %d for part %d" % (i+1, FramesPerCycle, part))

                    #measure time and memory usage
                    print("Frame process time: " + str(time.time()-process_start))
                    print('RAM memory % used:', psutil.virtual_memory()[2])

                    #failsafe in case memory runs out
                    if psutil.virtual_memory()[2] > 95.0:
                        break

                except PySpin.SpinnakerException as ex:
                    print('Error: %s' % ex)
                    result = False

            vid.release()

            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Save the recorded data as a WAV file
            wf = wave.open(audio_filename, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(sample_format))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(sound_frames))
            wf.close()

            print('Video saved at %s' % video_filename)
            print("Sound saved at %s" % audio_filename)

            combine_audio_video(video_filename, audio_filename, vidaudio_filename)



        cam.EndAcquisition()


    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def combine_audio_video(vid_filename, aud_filename, vidaud_filename, fps = FramerateToSet):
    combine_start = time.time()
    import ffmpeg
    print('--- ffmpeg ---')
    video  = ffmpeg.input(vid_filename).video # get only video channel
    audio  = ffmpeg.input(aud_filename).audio # get only audio channel
    output = ffmpeg.output(video, audio, vidaud_filename, vcodec='copy', acodec='aac', strict='experimental')
    ffmpeg.run(output)
    print("Combine time: " + str(time.time()-combine_start))


def print_device_info(nodemap):
    #this function only prints device info and parameters
    try:
        result = True
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

        if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('%s: %s' % (node_feature.GetName(),
                                  node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('Device control information not available.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result

def run_single_camera(cam):
    try:
        result = True

        nodemap_tldevice = cam.GetTLDeviceNodeMap()

        result &= print_device_info(nodemap_tldevice)

        cam.Init()

        nodemap = cam.GetNodeMap()

        err = acquire_and_save(cam, nodemap)
        if err < 0:
            return err

        # Deinitialize camera
        cam.DeInit()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def main():
    result = True

    system = PySpin.System.GetInstance()

    version = system.GetLibraryVersion()
    print('Library version: %d.%d.%d.%d' % (version.major, version.minor, version.type, version.build))

    cam_list = system.GetCameras()

    if not cam_list.GetSize() == 0:
        print("Camera detected")
    else:
        cam_list.Clear()
        system.ReleaseInstance()

        print('No camera detected')
        input('Done! Press Enter to exit...')

        return False
    
    for i, cam in enumerate(cam_list):

        print('Running example for camera %d...' % i)

        result &= run_single_camera(cam)
        print('Camera %d example complete... \n' % i)

    print("Recording complete...")

    cam_list.Clear()
    del cam
    system.ReleaseInstance()

    input('Done! Press Enter to exit...')
    return result
    

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)