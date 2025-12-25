#!/usr/bin/env python3
import cv2
import numpy as np
import json
from typing import Dict, List, Any, Optional

class VideoVisualizer:
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.current_analysis = None
        
        # Colors for visualization
        self.colors = {
            'lane_lines': (0, 255, 0),      # Green
            'path': (255, 0, 0),            # Blue  
            'lead_vehicle': (0, 0, 255),    # Red
            'road_edges': (255, 255, 0),    # Cyan
            'text': (255, 255, 255)         # White
        }
    
    def update_analysis(self, analysis: Dict[str, Any]):
        """Update current analysis data"""
        self.current_analysis = analysis
    
    def draw_lane_lines(self, frame: np.ndarray, lane_lines: List[Dict]):
        """Draw detected lane lines"""
        for lane in lane_lines:
            if lane['confidence'] > 0.3:  # Only draw confident lanes
                points = np.array(lane['points'], dtype=np.int32)
                if len(points) > 1:
                    # Convert to image coordinates (simplified)
                    points[:, 0] = points[:, 0] * 10 + frame.shape[1] // 2
                    points[:, 1] = frame.shape[0] - points[:, 1] * 10
                    
                    # Clip to frame bounds
                    points[:, 0] = np.clip(points[:, 0], 0, frame.shape[1] - 1)
                    points[:, 1] = np.clip(points[:, 1], 0, frame.shape[0] - 1)
                    
                    cv2.polylines(frame, [points], False, self.colors['lane_lines'], 2)
                    
                    # Draw confidence
                    if len(points) > 0:
                        cv2.putText(frame, f"{lane['confidence']:.2f}", 
                                  tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                                  self.colors['text'], 1)
    
    def draw_path_prediction(self, frame: np.ndarray, path_data: Dict):
        """Draw predicted path"""
        if 'path_points' not in path_data or not path_data['path_points']:
            return
        
        points = np.array(path_data['path_points'], dtype=np.int32)
        if len(points) > 1:
            # Convert to image coordinates
            points[:, 0] = points[:, 0] * 10 + frame.shape[1] // 2
            points[:, 1] = frame.shape[0] - points[:, 1] * 10
            
            # Clip to frame bounds
            points[:, 0] = np.clip(points[:, 0], 0, frame.shape[1] - 1)
            points[:, 1] = np.clip(points[:, 1], 0, frame.shape[0] - 1)
            
            cv2.polylines(frame, [points], False, self.colors['path'], 3)
    
    def draw_lead_vehicles(self, frame: np.ndarray, lead_vehicles: List[Dict]):
        """Draw lead vehicle indicators"""
        for i, lead in enumerate(lead_vehicles):
            if lead['probability'] > 0.5:
                # Calculate position on screen
                x = int(frame.shape[1] // 2 + lead['lateral_offset'] * 10)
                y = int(frame.shape[0] - lead['distance'] * 2)
                
                # Clip to frame bounds
                x = max(0, min(x, frame.shape[1] - 1))
                y = max(0, min(y, frame.shape[0] - 1))
                
                # Draw bounding box
                box_size = 30
                cv2.rectangle(frame, 
                            (x - box_size, y - box_size), 
                            (x + box_size, y + box_size), 
                            self.colors['lead_vehicle'], 2)
                
                # Draw info text
                info_text = f"Lead {i}: {lead['distance']:.1f}m"
                cv2.putText(frame, info_text, (x - box_size, y - box_size - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['text'], 1)
    
    def draw_road_edges(self, frame: np.ndarray, road_edges: List[Dict]):
        """Draw road edges"""
        for edge in road_edges:
            if edge['confidence'] > 0.3:
                points = np.array(edge['points'], dtype=np.int32)
                if len(points) > 1:
                    # Convert to image coordinates
                    points[:, 0] = points[:, 0] * 10 + frame.shape[1] // 2
                    points[:, 1] = frame.shape[0] - points[:, 1] * 10
                    
                    # Clip to frame bounds
                    points[:, 0] = np.clip(points[:, 0], 0, frame.shape[1] - 1)
                    points[:, 1] = np.clip(points[:, 1], 0, frame.shape[0] - 1)
                    
                    cv2.polylines(frame, [points], False, self.colors['road_edges'], 1)
    
    def draw_info_panel(self, frame: np.ndarray, analysis: Dict[str, Any]):
        """Draw information panel"""
        info_y = 30
        line_height = 25
        
        # Background for info panel
        cv2.rectangle(frame, (10, 10), (400, 200), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (400, 200), self.colors['text'], 1)
        
        # Frame info
        cv2.putText(frame, f"Frame: {analysis['frame_id']}", 
                   (20, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['text'], 1)
        info_y += line_height
        
        # Model performance
        cv2.putText(frame, f"Model time: {analysis['model_execution_time']:.1f}ms", 
                   (20, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['text'], 1)
        info_y += line_height
        
        # Detection counts
        lane_count = len(analysis['lane_lines'])
        lead_count = len(analysis['lead_vehicles'])
        cv2.putText(frame, f"Lanes: {lane_count}, Leads: {lead_count}", 
                   (20, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['text'], 1)
        info_y += line_height
        
        # Engagement status
        engaged_text = "ENGAGED" if analysis.get('engaged', False) else "DISENGAGED"
        color = (0, 255, 0) if analysis.get('engaged', False) else (0, 0, 255)
        cv2.putText(frame, engaged_text, (20, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    def visualize_frame(self) -> Optional[np.ndarray]:
        """Get current frame with analysis overlay"""
        ret, frame = self.cap.read()
        if not ret or self.current_analysis is None:
            return None
        
        # Draw all analysis elements
        self.draw_lane_lines(frame, self.current_analysis['lane_lines'])
        self.draw_path_prediction(frame, self.current_analysis['path_prediction'])
        self.draw_lead_vehicles(frame, self.current_analysis['lead_vehicles'])
        self.draw_road_edges(frame, self.current_analysis['road_edges'])
        self.draw_info_panel(frame, self.current_analysis)
        
        return frame
    
    def show_live(self):
        """Show live visualization window"""
        cv2.namedWindow('Openpilot Analysis', cv2.WINDOW_AUTOSIZE)
        
        while True:
            frame = self.visualize_frame()
            if frame is None:
                break
            
            cv2.imshow('Openpilot Analysis', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):  # Pause/resume
                cv2.waitKey(0)
        
        cv2.destroyAllWindows()
    
    def save_visualization_video(self, output_path: str, analysis_results: List[Dict]):
        """Save visualization as video file"""
        # Reset video capture
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # Get video properties
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        print(f"Creating visualization video: {output_path}")
        
        for i, analysis in enumerate(analysis_results):
            self.current_analysis = analysis
            frame = self.visualize_frame()
            
            if frame is not None:
                out.write(frame)
            
            if i % 100 == 0:
                print(f"Processed {i}/{len(analysis_results)} frames")
        
        out.release()
        print(f"Visualization video saved: {output_path}")
    
    def __del__(self):
        if hasattr(self, 'cap') and self.cap:
            self.cap.release()