#-*- coding: utf-8 -*-
import numpy as np
import cv2
import keras
from keras.preprocessing.image import ImageDataGenerator
import tensorflow as tf
import time 

model = keras.models.load_model(r"model.h5")


word_dict = {0:'1',1:'2',2:'3',3:'4',4:'5',5:'6',6:'7',7:'8',8:'9',9:'done',10:'notdone'}

admk=0
dmk=0
bjp=0
dmdk=0
congress=0
display=True
background = None
accumulated_weight = 0.5

ROI_top = 100         #10
ROI_bottom = 300       #350
ROI_right = 150        #10
ROI_left = 350         #350

def cal_accum_avg(frame, accumulated_weight):

    global background
    
    if background is None:
        background = frame.copy().astype("float")
        return None

    cv2.accumulateWeighted(frame, background, accumulated_weight)


def segment_hand(frame, threshold=25):
    global background
    
    diff = cv2.absdiff(background.astype("uint8"), frame)

    
    _ ,thresholded = cv2.threshold(diff, threshold, 255,cv2.THRESH_BINARY)
    
     #Fetching contours in the frame (These contours can be of hand
#or any other object in foreground) …

    contours, hierarchy =cv2.findContours(thresholded.copy(),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

    # If length of contours list = 0, means we didn't get any
   # contours...
    if len(contours) == 0:
        return None
        
    else:
        # The largest external contour should be the hand 
        hand_segment_max_cont = max(contours, key=cv2.contourArea)
        
        # Returning the hand segment(max contour) and the
 # thresholded image of hand...
        return (thresholded, hand_segment_max_cont)

def play(words):
    converter.say(words)
    converter.runAndWait()


cam = cv2.VideoCapture(0)
num_frames =0
i=0
while True:
    ret, frame = cam.read()
    
    # flipping the frame to prevent inverted image of captured
   # frame...
    
    frame = cv2.flip(frame, 1)

    frame_copy = frame.copy()

    # ROI from the frame
    roi = frame[ROI_top:ROI_bottom, ROI_right:ROI_left]

    gray_frame = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray_frame = cv2.GaussianBlur(gray_frame, (9, 9), 0)


    if num_frames < 70:
        
        cal_accum_avg(gray_frame, accumulated_weight)
        
        cv2.putText(frame_copy, "FETCHING BACKGROUND...PLEASE WAIT", (80, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)
        
    else: 
        # segmenting the hand region
        hand = segment_hand(gray_frame)
        
        # Checking if we are able to detect the hand...
        if hand is not None:
            
            thresholded, hand_segment = hand

            # Drawing contours around hand segment
            cv2.drawContours(frame_copy, [hand_segment + (ROI_right, ROI_top)], -1, (255, 0, 0),1)
            
            cv2.imshow("Thesholded Hand Image", thresholded)
            
            thresholded = cv2.resize(thresholded, (64, 64))
            thresholded = cv2.cvtColor(thresholded,cv2.COLOR_GRAY2RGB)
            thresholded = np.reshape(thresholded,(1,thresholded.shape[0],thresholded.shape[1],3))
            i=i+1
            if(display==True):
                print("we have 5 parties\n1 for bjp\n2 for admk\n3 for dmk\4 for congress\n5 for dmdk")
                display=False
            if i==60:
                pred = model.predict(thresholded)
                cv2.putText(frame_copy, word_dict[np.argmax(pred)],(170, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                words = ""
                words = word_dict[np.argmax(pred)]
                
                if (words=="1"):
                    bjp=bjp+1
                    print(f"bjp={bjp}")
                elif(words=="2"):
                    admk=admk+1
                    print(f"admk={admk}")
                elif(words=="3"):
                    dmk=dmk+1
                    print(f"dmk={dmk}")
                elif(words=="4"):
                    congress=congress+1
                    print(f"congress={congress}")
                elif(words=="5"):
                    dmdk=dmdk+1
                    print(f"dmdk={dmdk}")
                #else:
                     #print(words)
                i=0

            # if i==15:
            #     i=0S
            
            
            
            
            
    # Draw ROI on frame_copy
    cv2.rectangle(frame_copy, (ROI_left, ROI_top), (ROI_right,
    ROI_bottom), (255,128,0), 3)

    # incrementing the number of frames for tracking
    num_frames += 1

    # Display the frame with segmented hand
    cv2.putText(frame_copy, "Hand gesture based voting system",
    (10, 20), cv2.FONT_ITALIC, 0.5, (51,255,51), 1)
    cv2.imshow("Sign Detection", frame_copy)
    # print()

    # Close windows with Esc
    k = cv2.waitKey(1) & 0xFF

    if k == 27:
        break

# Release the camera and destroy all the windows
cam.release()
cv2.destroyAllWindows()