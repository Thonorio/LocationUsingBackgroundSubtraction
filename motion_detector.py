# import the necessary packages
from imutils.video import VideoStream
import argparse
import datetime
import imutils
import time
import cv2
import requests
import uuid
import json
import random

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to the video file")
ap.add_argument("-a", "--min-area", type=int, default=500, help="minimum area size")
ap.add_argument("-l", "--location", default="Room " + str(random.random()), help="Camera location")
ap.add_argument("-s", "--slow-mode", type=bool, default=bool(False), help="Slow Mode, capture image every 30 secs")
args = vars(ap.parse_args())


SENSOR_ENDPOINT = "http://localhost:8080/sensors"

resp = requests.get(url = SENSOR_ENDPOINT)

if resp.status_code != 200:
    # This means something went wrong.
    raise ApiError('GET /tasks/ {}'.format(resp.status_code))


print("Of the following sensors, wich is on this room:")

iteration = 1

optionsMap = {}

print("0: None")

for item in resp.json():
	json_str = json.dumps(item)
	value = json.loads(json_str)['name']
	print(iteration,": ", value)
	optionsMap[iteration] = value
	iteration = iteration + 1

optionSelected = int(input("Enter a number: "))


############################################################################ Register Location ############################################################################

# Create uuid
UUID = str(uuid.uuid4())

# Create state variabels 
currentState = bool(False)
pastState = bool(False)
lastsave = 0

# Api-endpoint 
CREATION_ENDPOINT = "http://localhost:8080/locations"
UPDATE_ENDPOINT = "http://localhost:8080/locations/" + UUID

if optionSelected != 0:
	print("Selected",  optionsMap[optionSelected])
	data = {'uuid': UUID,
		'name': "Camera-" + UUID, 
        'location': args.get("location"), 
		'sensor' : optionsMap[optionSelected],
        'occupied': currentState}
else:
	data = {'uuid': UUID,
		'name': "Camera-" + UUID, 
        'location': args.get("location"), 
        'occupied': currentState}

creationRequest = requests.post(url = CREATION_ENDPOINT, json = data)
 

############################################################################ Camera Detection ############################################################################

# if the video argument is None, then we are reading from webcam
if args.get("video", None) is None:
	vs = VideoStream(src=0).start()
	time.sleep(2.0)

# otherwise, we are reading from a video file
else:
	vs = cv2.VideoCapture(args["video"])

# initialize the first frame in the video stream
firstFrame = None

# loop over the frames of the video
while True:
	# grab the current frame and initialize the occupied/unoccupied
	# text
	frame = vs.read()
	frame = frame if args.get("video", None) is None else frame[1]
	text = "Unoccupied"
	currentState = bool(False)

	# if the frame could not be grabbed, then we have reached the end
	# of the video
	if frame is None:
		break

	# resize the frame, convert it to grayscale, and blur it
	frame = imutils.resize(frame, width=500)
	gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
	gray = cv2.GaussianBlur(gray, (21, 21), 0)

	# if the first frame is None, initialize it
	if firstFrame is None:
		firstFrame = gray
		continue

	# compute the absolute difference between the current frame and
	# first frame
	frameDelta = cv2.absdiff(firstFrame, gray)
	thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]

	# dilate the thresholded image to fill in holes, then find contours
	# on thresholded image
	thresh = cv2.dilate(thresh, None, iterations=2)
	cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE)
	cnts = imutils.grab_contours(cnts)

	# loop over the contours
	for c in cnts:
		# if the contour is too small, ignore it
		if cv2.contourArea(c) < args["min_area"]:
			continue

		# compute the bounding box for the contour, draw it on the frame,
		# and update the text
		(x, y, w, h) = cv2.boundingRect(c)
		cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
		text = "Occupied"
		currentState = bool(True)

	# draw the text and timestamp on the frame
	cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
		cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
	cv2.putText(frame, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),
		(10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

	# show the frame and record if the user presses a key
	cv2.imshow("Security Feed", frame)
	cv2.imshow("Thresh", thresh)
	cv2.imshow("Frame Delta", frameDelta)
	key = cv2.waitKey(1) & 0xFF

	if currentState != pastState and time.time() - lastsave > 3:
		if optionSelected != 0:
			data = {'uuid': UUID,
			'name': "Camera-" + UUID, 
			'location': args.get("location"), 
			'sensor' : optionsMap[optionSelected],
			'occupied': currentState}
		else:
			data = {'uuid': UUID,
			'name': "Camera-" + UUID, 
			'location': args.get("location"), 
			'occupied': currentState}
		creationRequest = requests.post(url = UPDATE_ENDPOINT, json = data)
		pastState = currentState
		lastsave = time.time()
	
	#if args.get("slow-mode"):
	#	time.sleep(30)

	# if the `q` key is pressed, break from the lop
	if key == ord("q"):
		break

# cleanup the camera and close any open windows
vs.stop() if args.get("video", None) is None else vs.release()
cv2.destroyAllWindows()
