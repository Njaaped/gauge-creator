# backend_logic.py
# This file contains all non-GUI functions, including parsing
# TCX files and preparing data for the video generator.

import json
import os
from datetime import datetime, timezone
from lxml import etree
import gauge_generator # Import for the orchestrator

def parse_tcx_file(tcx_path):
    """
    Parses a TCX file to extract trackpoints (time, power, hr, cad, speed).
    Raises ValueError with a descriptive message on failure.
    """
    try:
        tree = etree.parse(tcx_path)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"File is not a valid XML/TCX file. Details: {e}")

    root = tree.getroot()

    # Define the main TCX namespace
    ns = {'tcx': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}

    trackpoints = []

    # Using XPath to find all Trackpoint elements
    all_tp_nodes = root.xpath('//tcx:Trackpoint', namespaces=ns)
    if not all_tp_nodes:
        raise ValueError("TCX file does not contain any Trackpoint data.")

    for tp in all_tp_nodes:
        time_str_nodes = tp.xpath('tcx:Time/text()', namespaces=ns)
        if not time_str_nodes:
            continue
        time_str = time_str_nodes[0]

        # Use xpath with local-name() to ignore namespaces for extension data
        power_nodes = tp.xpath(".//*[local-name()='Watts']/text()")
        power_str = power_nodes[0] if power_nodes else '0'

        hr_nodes = tp.xpath(".//*[local-name()='HeartRateBpm']/*[local-name()='Value']/text()")
        hr_str = hr_nodes[0] if hr_nodes else '0'

        cad_nodes = tp.xpath('tcx:Cadence/text()', namespaces=ns)
        cad_str = cad_nodes[0] if cad_nodes else '0'
        
        dist_nodes = tp.xpath('tcx:DistanceMeters/text()', namespaces=ns)
        dist_str = dist_nodes[0] if dist_nodes else None

        # Try parsing datetime with and without fractional seconds
        time = None
        try:
            time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            except ValueError:
                # If both fail, skip this trackpoint
                print(f"Warning: Skipping trackpoint with unparsable time: {time_str}")
                continue
        
        trackpoints.append({
            'time': time,
            'power': int(power_str or 0),
            'hr': int(hr_str or 0),
            'cadence': int(cad_str or 0),
            'distance': float(dist_str) if dist_str is not None else None
        })

    if not trackpoints:
        raise ValueError("Successfully parsed TCX file, but no valid trackpoints with recognized timestamps were found.")
        
    # Calculate speed based on distance and time differences
    for i in range(len(trackpoints)):
        if i > 0 and trackpoints[i]['distance'] is not None and trackpoints[i-1]['distance'] is not None:
            dist_delta = trackpoints[i]['distance'] - trackpoints[i-1]['distance']
            time_delta = (trackpoints[i]['time'] - trackpoints[i-1]['time']).total_seconds()
            if time_delta > 0:
                speed_ms = dist_delta / time_delta
                trackpoints[i]['speed'] = speed_ms
            else:
                trackpoints[i]['speed'] = trackpoints[i-1].get('speed', 0)
        else:
            trackpoints[i]['speed'] = 0

    start_time = trackpoints[0]['time'].astimezone(None)
    end_time = trackpoints[-1]['time'].astimezone(None)

    return {
        'start_time': start_time,
        'end_time': end_time,
        'trackpoints': trackpoints
    }


def slice_data_and_save_json(trackpoints, start_time, end_time, output_path):
    """
    Filters the trackpoints to a given time range and saves as a JSON file.
    """
    
    # Robustly convert incoming start/end times to aware UTC objects.
    if start_time.tzinfo is None:
        start_time_utc = start_time.astimezone().astimezone(timezone.utc)
    else:
        start_time_utc = start_time.astimezone(timezone.utc)

    if end_time.tzinfo is None:
        end_time_utc = end_time.astimezone().astimezone(timezone.utc)
    else:
        end_time_utc = end_time.astimezone(timezone.utc)

    sliced_data = []
    for tp in trackpoints:
        # The comparison is now a direct, correct comparison of two UTC times.
        if start_time_utc <= tp['time'] <= end_time_utc:
            data_point = tp.copy()
            data_point['time'] = tp['time'].isoformat()
            sliced_data.append(data_point)
            
    with open(output_path, 'w') as f:
        json.dump(sliced_data, f, indent=2)

    print(f"Sliced data saved to {output_path}")

def orchestrate_video_generation(tcx_data, start_time, end_time, output_path, progress_callback):
    """
    Orchestrates the entire video generation process from slicing to completion.
    This is the single source of truth for the generation logic.
    
    Args:
        tcx_data (list): The list of trackpoint dictionaries.
        start_time (datetime): The start time for the video segment.
        end_time (datetime): The end time for the video segment.
        output_path (str): The final path to save the MP4 video.
        progress_callback (function): A function to call with progress updates.
                                      It should accept two arguments: (percentage, message).
    """
    # Use a unique name for the temp file to avoid conflicts
    temp_json_path = f"temp_sliced_data_{os.path.basename(output_path)}.json"
    
    try:
        # 1. Slice the data
        progress_callback(10, "Slicing TCX data...")
        slice_data_and_save_json(tcx_data, start_time, end_time, temp_json_path)

        # 2. Generate the video
        # This nested adapter scales progress from gauge_generator (0-100)
        # to the remainder of our progress bar (e.g., 20-95).
        def video_progress_adapter(p, m):
            scaled_progress = 20 + int((p / 100) * 75) # Scale 0-100 to 20-95
            progress_callback(scaled_progress, m)

        progress_callback(20, "Generating gauge video frames...")
        gauge_generator.create_gauge_video(
            temp_json_path, 
            output_path, 
            progress_callback=video_progress_adapter
        )
        
        # 3. Finalize
        progress_callback(100, "Video generation complete.")
        return output_path

    finally:
        # 4. Cleanup
        if os.path.exists(temp_json_path):
            os.remove(temp_json_path)