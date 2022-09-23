import PySpin
import sys
import datetime
import numpy as np
import time
import cv2
from PIL import Image as im
import moviepy.video.io.ImageSequenceClip as mp
import os, psutil


###############################################################################
####################### GLOBAL PARAMETER SETTINGS #############################

VideoFormat = PySpin.H264Option  #leave it as is to record mp4 format videos

FramerateToSet = 10    #this will change the camera's acquisiton framerate and also the videofile framerate, but should not be more than 30
SecondsToRecord = 10  #change this number according to how long you want your video file to be
PartsToRecord = 1     #how many times you want to record. e.g. 3pcs of 1 hour video
VideoBitrate = 1000000  #change this to the wanted bitrate of the video file // 1Mbit should be OK
ScaleUpperLimit = 310.0
ScaleLowerLimit = 290.0

NUM_IMAGES = SecondsToRecord * FramerateToSet
ImageHeight = 480
ImageWidth = 640
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

        #images = list()
        #processor = PySpin.ImageProcessor()
        #processor.SetColorProcessing(PySpin.HQ_LINEAR)


        print('Frame rate to be set to %d...' % FramerateToSet)

        vid_filename = "Record" + "_{date:%Y-%m-%d_%H:%M:%S}".format(date=datetime.datetime.now()) + ".mp4"
        size = (640, 480)
        vid = cv2.VideoWriter(vid_filename,cv2.VideoWriter_fourcc(*'mp4v'), FramerateToSet, size)


        for i in range(NUM_IMAGES):
            try:
                process_start = time.time()

                image_result = cam.GetNextImage(1000)

                if image_result.IsIncomplete():
                    print("Image %d is incomplete. Status: %d" % (i, image_result.GetImageStatus()))

                else:
                    #width = image_result.GetWidth()
                    #height = image_result.GetHeight()
                    print("Grabbed image %d" % i)


                    image_data = image_result.GetNDArray()
                    image_result.Release()

                    #image_data = np.array(image_data)
                    image_data = image_data - 23900
                    image_data = cv2.convertScaleAbs(image_data, alpha=(255.0/2200.0))

                    image_data = cv2.cvtColor(image_data, cv2.COLOR_GRAY2BGR)

                    vid.write(image_data)

                    #images.append(image_data)



                    print("Appended image %d of %d" % (i, NUM_IMAGES))

                print("Frame process time: " + str(time.time()-process_start))
                print('RAM memory % used:', psutil.virtual_memory()[2])
                if psutil.virtual_memory()[2] > 95.0:
                    break

            except PySpin.SpinnakerException as ex:
                print('Error: %s' % ex)
                result = False


        #for i in range(len(images)):
        #    vid.write(images[i])

        vid.release()


        #vid = mp.ImageSequenceClip(images, fps=FramerateToSet)
        #vid.write_videofile('my_video.mp4')

        cam.EndAcquisition()
        #vid.release()


        print('Video saved at %s.mp4' % vid_filename)

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def print_device_info(nodemap):
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

        #result &= save_list_to_avi(nodemap_tldevice, images)

                    #part = 0
                    #while part < PartsToRecord:
                    #    part += 1
                    #
                    #    # Acquire list of images
                    #    err, images = acquire_images(cam, nodemap)
                    #    if err < 0:
                    #        return err
                    #
                    #    # Save the image list to file
                    #    result &= save_list_to_avi(nodemap_tldevice, images, part)

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