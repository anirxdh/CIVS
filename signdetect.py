#-*- coding: utf-8 -*-
import numpy as np
import cv2
import keras
from keras.preprocessing.image import ImageDataGenerator
import tensorflow as tf
import time 
import pyttsx3
import tkinter as tk
from tkinter import messagebox
import threading

# Initialize text-to-speech engine
converter = pyttsx3.init()

model = keras.models.load_model(r"model.h5")

word_dict = {0:'1',1:'2',2:'3',3:'4',4:'5',5:'6',6:'7',7:'8',8:'9',9:'done',10:'notdone'}

# Global vote counts (shared with main.py)
vote_counts = {
    'BJP': 0,
    'ADMK': 0,
    'DMK': 0,
    'Congress': 0,
    'DMDK': 0
}

# Party mapping
parties = {
    '1': 'BJP',
    '2': 'ADMK', 
    '3': 'DMK',
    '4': 'Congress',
    '5': 'DMDK'
}

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
    
    contours, hierarchy =cv2.findContours(thresholded.copy(),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) == 0:
        return None
        
    else:
        hand_segment_max_cont = max(contours, key=cv2.contourArea)
        return (thresholded, hand_segment_max_cont)

def play(words):
    converter.say(words)
    converter.runAndWait()

def confirm_vote_gesture(party_name):
    """Ask user to confirm their vote via GUI"""
    return messagebox.askyesno("Confirm Vote", f"Do you want to vote for {party_name}?")

def update_vote_count(party_name):
    """Update vote count for the selected party"""
    if party_name in vote_counts:
        vote_counts[party_name] += 1
        messagebox.showinfo("Vote Recorded", f"Your vote for {party_name} has been recorded!\n\nCurrent Vote Counts:\n" + 
                          "\n".join([f"{party}: {count}" for party, count in vote_counts.items()]))

def gesture_voting_system():
    """Main gesture voting system with GUI integration"""
    cam = cv2.VideoCapture(0)
    num_frames = 0
    i = 0
    last_detected = None
    confirmation_mode = False
    selected_party = None
    
    while True:
        ret, frame = cam.read()
        
        if not ret:
            print("Failed to grab frame")
            break
            
        frame = cv2.flip(frame, 1)
        frame_copy = frame.copy()

        # ROI from the frame
        roi = frame[ROI_top:ROI_bottom, ROI_right:ROI_left]

        gray_frame = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray_frame = cv2.GaussianBlur(gray_frame, (9, 9), 0)

        if num_frames < 70:
            cal_accum_avg(gray_frame, accumulated_weight)
            cv2.putText(frame_copy, "FETCHING BACKGROUND...PLEASE WAIT", (80, 400), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)
        else: 
            hand = segment_hand(gray_frame)
            
            if hand is not None:
                thresholded, hand_segment = hand
                cv2.drawContours(frame_copy, [hand_segment + (ROI_right, ROI_top)], -1, (255, 0, 0),1)
                cv2.imshow("Thresholded Hand Image", thresholded)
                
                thresholded = cv2.resize(thresholded, (64, 64))
                thresholded = cv2.cvtColor(thresholded,cv2.COLOR_GRAY2RGB)
                thresholded = np.reshape(thresholded,(1,thresholded.shape[0],thresholded.shape[1],3))
                i = i + 1
                
                if display:
                    print("Hand Gesture Voting Instructions:")
                    print("1 finger = BJP")
                    print("2 fingers = ADMK")  
                    print("3 fingers = DMK")
                    print("4 fingers = Congress")
                    print("5 fingers = DMDK")
                    print("Show 'done' gesture to confirm vote")
                    display = False
                
                if i == 60:  # Every 60 frames, make a prediction
                    pred = model.predict(thresholded)
                    detected_gesture = word_dict[np.argmax(pred)]
                    cv2.putText(frame_copy, detected_gesture, (170, 45), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                    
                    # Handle vote detection and confirmation
                    if detected_gesture in parties and not confirmation_mode:
                        selected_party = parties[detected_gesture]
                        cv2.putText(frame_copy, f"Detected: {selected_party}", (10, 80), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                        cv2.putText(frame_copy, "Show 'done' gesture to confirm", (10, 110), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
                        last_detected = detected_gesture
                    
                    elif detected_gesture == 'done' and selected_party and not confirmation_mode:
                        confirmation_mode = True
                        cv2.putText(frame_copy, "CONFIRMING VOTE...", (10, 140), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
                        
                        # Ask for confirmation in a separate thread
                        def confirm_vote():
                            if confirm_vote_gesture(selected_party):
                                update_vote_count(selected_party)
                                print(f"Vote recorded for {selected_party}")
                            else:
                                print("Vote cancelled")
                        
                        threading.Thread(target=confirm_vote, daemon=True).start()
                        selected_party = None
                        confirmation_mode = False
                    
                    i = 0
            
        # Draw ROI on frame_copy
        cv2.rectangle(frame_copy, (ROI_left, ROI_top), (ROI_right, ROI_bottom), (255,128,0), 3)

        # Display instructions
        cv2.putText(frame_copy, "Hand Gesture Voting System", (10, 20), 
                   cv2.FONT_ITALIC, 0.5, (51,255,51), 1)
        
        if selected_party:
            cv2.putText(frame_copy, f"Selected: {selected_party}", (10, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

        num_frames += 1
        cv2.imshow("Sign Detection", frame_copy)

        # Close windows with Esc
        k = cv2.waitKey(1) & 0xFF
        if k == 27:
            break

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    gesture_voting_system()