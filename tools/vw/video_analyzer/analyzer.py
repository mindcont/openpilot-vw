#!/usr/bin/env python3
import time
import json
from typing import Dict, List, Optional, Any

import cereal.messaging as messaging
from cereal import log

class OpenpilotAnalyzer:
    def __init__(self):
        # Subscribe to openpilot outputs
        self.sm = messaging.SubMaster([
            'modelV2',           # Road model predictions
            'liveCalibration',   # Camera calibration
            'carState',          # Vehicle state
            'controlsState',     # Control state
            'lateralPlan',       # Lateral planning
            'longitudinalPlan',  # Longitudinal planning
            'roadCameraState'    # Camera state
        ])
        
        self.results = []
        self.frame_count = 0
    
    def extract_lane_lines(self, model_data) -> List[Dict]:
        """Extract lane line information"""
        lanes = []
        for i, lane in enumerate(model_data.laneLines):
            if len(lane.t) > 0:
                lanes.append({
                    'lane_id': i,
                    'confidence': float(lane.prob),
                    'points': [[float(x), float(y)] for x, y in zip(lane.x, lane.y)],
                    'std': float(lane.std) if hasattr(lane, 'std') else 0.0
                })
        return lanes
    
    def extract_lead_vehicles(self, model_data) -> List[Dict]:
        """Extract lead vehicle information"""
        leads = []
        for i, lead in enumerate(model_data.leads):
            if lead.prob > 0.1:  # Only include confident detections
                leads.append({
                    'lead_id': i,
                    'probability': float(lead.prob),
                    'distance': float(lead.x[0]) if len(lead.x) > 0 else 0.0,
                    'relative_velocity': float(lead.v[0]) if len(lead.v) > 0 else 0.0,
                    'lateral_offset': float(lead.y[0]) if len(lead.y) > 0 else 0.0,
                    'acceleration': float(lead.a[0]) if len(lead.a) > 0 else 0.0
                })
        return leads
    
    def extract_path_prediction(self, model_data) -> Dict:
        """Extract path prediction information"""
        if len(model_data.position.x) == 0:
            return {}
        
        return {
            'path_points': [[float(x), float(y)] for x, y in zip(model_data.position.x, model_data.position.y)],
            'path_std': [float(s) for s in model_data.position.xStd] if len(model_data.position.xStd) > 0 else [],
            'velocity_profile': [float(v) for v in model_data.velocity.x] if len(model_data.velocity.x) > 0 else [],
            'orientation': [float(o) for o in model_data.orientation.x] if len(model_data.orientation.x) > 0 else []
        }
    
    def extract_road_edges(self, model_data) -> List[Dict]:
        """Extract road edge information"""
        edges = []
        for i, edge in enumerate(model_data.roadEdges):
            if len(edge.t) > 0:
                edges.append({
                    'edge_id': i,
                    'confidence': float(edge.prob),
                    'points': [[float(x), float(y)] for x, y in zip(edge.x, edge.y)],
                    'std': float(edge.std) if hasattr(edge, 'std') else 0.0
                })
        return edges
    
    def analyze_frame(self) -> Optional[Dict[str, Any]]:
        """Analyze current frame and return results"""
        self.sm.update()
        
        if not self.sm.updated['modelV2']:
            return None
        
        model = self.sm['modelV2']
        timestamp = time.time()
        
        # Extract all analysis data
        analysis = {
            'frame_id': self.frame_count,
            'timestamp': timestamp,
            'model_execution_time': float(model.modelExecutionTime),
            'frame_drop_perc': float(model.frameDropPerc),
            
            # Core predictions
            'lane_lines': self.extract_lane_lines(model),
            'lead_vehicles': self.extract_lead_vehicles(model),
            'path_prediction': self.extract_path_prediction(model),
            'road_edges': self.extract_road_edges(model),
            
            # Additional data
            'desire_state': int(model.meta.desireState) if hasattr(model.meta, 'desireState') else 0,
            'engaged': bool(model.meta.engaged) if hasattr(model.meta, 'engaged') else False,
            'gas_disengage': bool(model.meta.gasDisengaged) if hasattr(model.meta, 'gasDisengaged') else False,
            'brake_disengage': bool(model.meta.brakeDisengaged) if hasattr(model.meta, 'brakeDisengaged') else False,
        }
        
        # Add calibration data if available
        if self.sm.updated['liveCalibration']:
            cal = self.sm['liveCalibration']
            analysis['calibration'] = {
                'rpy': [float(x) for x in cal.rpyCalib],
                'valid_blocks': int(cal.validBlocks)
            }
        
        self.results.append(analysis)
        self.frame_count += 1
        
        return analysis
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the analysis"""
        if not self.results:
            return {}
        
        total_frames = len(self.results)
        frames_with_lanes = sum(1 for r in self.results if r['lane_lines'])
        frames_with_leads = sum(1 for r in self.results if r['lead_vehicles'])
        
        avg_execution_time = sum(r['model_execution_time'] for r in self.results) / total_frames
        avg_frame_drop = sum(r['frame_drop_perc'] for r in self.results) / total_frames
        
        return {
            'total_frames': total_frames,
            'lane_detection_rate': frames_with_lanes / total_frames,
            'lead_detection_rate': frames_with_leads / total_frames,
            'avg_model_execution_time_ms': avg_execution_time,
            'avg_frame_drop_percentage': avg_frame_drop,
            'analysis_duration': self.results[-1]['timestamp'] - self.results[0]['timestamp'] if total_frames > 1 else 0
        }
    
    def save_results(self, output_path: str):
        """Save analysis results to JSON file"""
        output_data = {
            'summary': self.get_summary_stats(),
            'frame_analysis': self.results
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Analysis results saved to {output_path}")
        print(f"Processed {len(self.results)} frames")
        print(f"Lane detection rate: {output_data['summary'].get('lane_detection_rate', 0):.2%}")
        print(f"Lead vehicle detection rate: {output_data['summary'].get('lead_detection_rate', 0):.2%}")