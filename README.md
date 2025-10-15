
-----

# Cycling Data Video Generator

A web application that takes a `.tcx` file from a cycling computer, visualizes the power data, and generates a dynamic video overlay for a selected time range. This is perfect for sharing highlights of your rides on social media.

This project uses **Flask** for the web backend, **Plotly.js** for interactive graphing, and **OpenCV/Pillow** for video and frame generation.

-----

## Features

  * **TCX File Parsing**: Upload and automatically parse `.tcx` files to extract key metrics like power, heart rate, and cadence.
  * **Interactive Data Visualization**: View your power data over time on an interactive graph. Zoom and pan to select the exact segment you want to turn into a video.
  * **Dynamic Video Generation**: Creates an MP4 video file with a "dashboard" overlay showing your power, W/kg, and an animated heart rate icon for the selected time range.
  * **Web-Based Interface**: Easy-to-use interface that runs entirely in your web browser. No desktop software installation is needed.
  * **Background Processing**: Video generation runs as a background task, allowing the UI to remain responsive and provide real-time progress updates.

-----

## Final Project Structure

The project has been simplified to contain only the web application components.

```
.
├── README.md
├── app.py                  # Main Flask application and API endpoints
├── backend_logic.py        # Handles TCX parsing and data processing
├── gauge_generator.py      # Core logic for creating video frames
├── requirements.txt        # Python package dependencies
├── assets/                 # Icons and fonts for the video overlay
│   ├── CartoonVibes-Regular.otf
│   ├── heart.png
│   └── lightning.png
└── templates/
    └── index.html          # Frontend HTML and JavaScript
```

-----

## Setup and Installation

### Prerequisites

  * Python 3.8+
  * `pip` for package management

### Instructions

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/GUIapplicatioon.git
    cd GUIapplicatioon
    ```

2.  **Create and activate a virtual environment (recommended):**

    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required packages:**

    ```bash
    pip install -r requirements.txt
    ```

-----

## How to Run

1.  **Start the Flask web server:**
    From the root directory of the project, run the following command:

    ```bash
    python app.py
    ```

2.  **Open the application in your browser:**
    Navigate to the following URL in your web browser:
    [http://127.0.0.1:5000](https://www.google.com/search?q=http://127.0.0.1:5000)

-----

## How to Use the Web App

1.  **Upload File**: Click the "Choose File" button and select a valid `.tcx` file from your computer.
2.  **Select Range**: Once the file is processed, an interactive graph of your power data will appear. Click and drag (or use your mouse wheel) to zoom and pan to the specific portion of the ride you want to feature. The start and end times below the graph will update automatically.
3.  **Generate Video**: Click the "Generate Video" button. The progress bar will show the status of the video creation process.
4.  **Download**: Once generation is complete, a download link will appear. Click it to save your `.mp4` video file.