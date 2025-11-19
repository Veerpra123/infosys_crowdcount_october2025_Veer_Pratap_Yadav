📊 CrowdCount – AI-Based People Counting & Monitoring System

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-%3E%3D2.0-orange)](https://flask.palletsprojects.com/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-red)](https://github.com/ultralytics/ultralytics)
[![License](https://img.shields.io/badge/Status-Prototype-green.svg)](https://github.com/your-repo)

Real-Time Detection • Tracking • Zone Monitoring • Alerts • Dashboard • Reports

CrowdCount is an AI-powered real-time people-counting and crowd-monitoring system built using Flask, YOLOv8, OpenCV, JavaScript, and HTML/CSS.
It detects people from camera or video feeds, assigns unique tracking IDs, monitors zone activity, generates alerts, and provides visual dashboards and exportable reports.

This project is designed for public safety, retail analytics, smart surveillance, and operational monitoring.

CrowdCount/
├── services/
│   ├── detector.py           # YOLOv8 detection + Simple Tracker
│   ├── video_stream.py       # Video streaming (camera/video)
│
├── static/
│   ├── admin.js              # Admin panel logic
│   ├── auth.js               # Login/Register logic
│   ├── script.js             # Dashboard (charts, live updates)
│   ├── style.css             # UI styling
│
├── templates/
│   ├── admin_cameras.html    # Camera feed monitoring
│   ├── admin_logs.html       # Alerts & activity logs
│   ├── admin_reports.html    # PDF/CSV report downloads
│   ├── dashboard.html        # User dashboard (live visualization)
│   ├── login.html            # Login screen
│   ├── register.html         # Signup screen
│
├── uploads/
│   ├── reports/              # Generated report files (PDF/CSV)
│   ├── *.mp4                 # Uploaded videos
│
├── app.db                    # SQLite database
├── app.py                    # Main Flask backend
├── requirements.txt
├── yolov8n.pt                # YOLOv8 model weights


🚀 Features
1. Real-Time Person Detection

YOLOv8 detects only “person” class

Works on webcam, IP camera, or uploaded video

2. Tracking with Unique IDs

Each person receives a unique ID

Tracks movements frame-to-frame

3. Zone Monitoring

User-defined polygons ("Danger Zones")

Calculates time spent inside zone

Tracks zone-wise population count

4. Automatic Alerts

Overcrowding alert

Zone crossing alert

Per-person risk alert

Alerts stored in DB

5. Live Dashboard

Line chart (total population)

Bar chart (zone population)

Map scatter plot (person positions)

Alerts panel

Person table with zone times

6. Admin Panel

Manage users

View logs

View alerts

Modify system thresholds

Download reports

7. PDF & CSV Reports

Individual PDF reports

Full alert history (CSV)

Stored inside /uploads/reports/

🛠️ Tech Stack
Backend

Flask

YOLOv8 (Ultralytics)

OpenCV-Python

Frontend

HTML, CSS

JavaScript (Fetch/AJAX)

Chart.js

Database

SQLite (app.db)

🧠 How It Works
1. Input

Live webcam feed

Uploaded video

IP camera stream

2. Detection + Tracking

services/detector.py loads YOLOv8

Runs people detection

Assigns unique IDs using SimpleTracker

Draws bounding boxes + labels

3. Frame Processing

video_stream.py converts frames → JPEG stream

Flask sends frames via /video endpoint

4. Dashboard API

Frontend fetches /person_data every 1 second

Updates:

charts

tables

alerts

5. Storage

Alerts + settings stored in app.db

6. Reports

PDF reports generated using ReportLab

CSV exported directly from DB

