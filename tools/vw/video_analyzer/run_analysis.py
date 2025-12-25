#!/usr/bin/env python3
import argparse
import os
import sys
import time
import signal
from pathlib import Path

# Add openpilot to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from video_input import VideoInput
from analyzer import OpenpilotAnalyzer
from visualizer import VideoVisualizer

class VideoAnalysisRunner:
    def __init__(self, video_path: str, output_path: str, visualize: bool = False, fps: float = 20.0):
        self.video_path = video_path
        self.output_path = output_path
        self.visualize = visualize
        self.fps = fps
        
        self.video_input = None
        self.analyzer = None
        self.visualizer = None
        self.running = True
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print("\nStopping analysis...")
        self.running = False
        if self.video_input:
            self.video_input.stop()
    
    def run(self):
        """Run the complete video analysis"""
        print(f"Starting analysis of: {self.video_path}")
        print(f"Output will be saved to: {self.output_path}")
        
        try:
            # Initialize components
            self.video_input = VideoInput(self.video_path, self.fps)
            self.analyzer = OpenpilotAnalyzer()
            
            if self.visualize:
                self.visualizer = VideoVisualizer(self.video_path)
            
            # Start video processing
            self.video_input.start()
            
            # Analysis loop
            last_progress_report = 0
            while self.running and self.video_input.running:
                # Analyze current frame
                analysis = self.analyzer.analyze_frame()
                
                if analysis:
                    # Show progress every 5%
                    progress = self.video_input.get_progress()
                    if progress - last_progress_report >= 0.05:
                        print(f"Progress: {progress:.1%} - Frame {analysis['frame_id']}")
                        if analysis['lane_lines']:
                            print(f"  Lanes detected: {len(analysis['lane_lines'])}")
                        if analysis['lead_vehicles']:
                            print(f"  Lead vehicles: {len(analysis['lead_vehicles'])}")
                        last_progress_report = progress
                    
                    # Update visualizer if enabled
                    if self.visualizer:
                        self.visualizer.update_analysis(analysis)
                
                time.sleep(0.01)  # Small delay to prevent busy waiting
            
            # Stop video processing
            self.video_input.stop()
            
            # Save results
            if self.analyzer.results:
                self.analyzer.save_results(self.output_path)
                
                # Show final summary
                summary = self.analyzer.get_summary_stats()
                print("\n=== Analysis Summary ===")
                print(f"Total frames processed: {summary.get('total_frames', 0)}")
                print(f"Lane detection rate: {summary.get('lane_detection_rate', 0):.2%}")
                print(f"Lead vehicle detection rate: {summary.get('lead_detection_rate', 0):.2%}")
                print(f"Average model execution time: {summary.get('avg_model_execution_time_ms', 0):.2f} ms")
                print(f"Analysis duration: {summary.get('analysis_duration', 0):.1f} seconds")
            else:
                print("No analysis results generated. Make sure openpilot models are running.")
        
        except Exception as e:
            print(f"Error during analysis: {e}")
            return False
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Analyze dashcam videos with openpilot')
    parser.add_argument('--video', required=True, help='Path to input video file')
    parser.add_argument('--output', required=True, help='Path to output JSON file')
    parser.add_argument('--visualize', action='store_true', help='Show real-time visualization')
    parser.add_argument('--fps', type=float, default=20.0, help='Processing FPS (default: 20)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        return 1
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Run analysis
    runner = VideoAnalysisRunner(args.video, args.output, args.visualize, args.fps)
    success = runner.run()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())