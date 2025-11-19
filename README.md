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
```
CrowdCount/
│
├── services/
│   ├── detector.py          # YOLOv8 detection + SimpleTracker
│   └── video_stream.py      # Video streaming (camera/video)
│
├── static/
│   ├── admin.js             # Admin panel logic
│   ├── auth.js              # Login/Register logic
│   ├── script.js            # Dashboard charts, live updates
│   └── style.css            # UI styling
│
├── templates/
│   ├── admin_cameras.html   # Camera feed monitoring
│   ├── admin_logs.html      # Alerts & activity logs
│   ├── admin_reports.html   # PDF/CSV report downloads
│   ├── dashboard.html       # User dashboard (live visualization)
│   ├── login.html           # Login screen
│   └── register.html        # Signup screen
│
├── uploads/
│   └── reports/             # Generated report files (PDF/CSV)
│
├── *.mp4                    # Uploaded video files
├── app.db                   # SQLite database
├── app.py                   # Main Flask backend
├── requirements.txt         # Python dependencies
└── yolov8n.pt               # YOLOv8 model weights
```

⭐ Features

CrowdCount provides a complete end-to-end AI system for real-time people monitoring, zone tracking, and safety alerts. The key features include:

1. Real-Time Person Detection

Uses YOLOv8 to detect individuals in camera or video streams with high accuracy.

2. Unique ID Tracking

Assigns each person a unique tracking ID and maintains consistent movement tracking across frames.

3. Zone Monitoring

Supports user-defined zones (Danger Zone / Safe Zone) and measures the time each person spends inside them.

4. Automated Alert System

Triggers alerts when thresholds are crossed:

Person inside danger zone for too long

Zone overcrowding

Overall population threshold exceeded

5. Live Dashboard

Displays real-time charts and visuals including:

Zone population bar chart

Overall population line graph

Person positions scatter plot

Live alerts panel

Detailed person table

6. Admin Panel

Role-based secure admin interface to:

Manage users

View alert logs

View system statistics

Modify system thresholds (live apply, no server restart required)

7. Authentication System

Secure login/register using hashed passwords and role-based access control.

8. PDF & CSV Reports

Generates:

Per-person PDF summaries

Complete CSV alert history

9. Video Stream Processing

Captures frames from camera/file and streams processed video to the dashboard.

10. Database Integration

Stores all users, alerts, and settings in SQLite (or PostgreSQL upgradable).
