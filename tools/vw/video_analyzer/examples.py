#!/usr/bin/env python3
"""
Example usage of the video analyzer
"""
import os
import sys
from pathlib import Path

# Add openpilot to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

def example_single_video():
    """Example: Analyze a single video"""
    print("=== Single Video Analysis Example ===")
    
    video_path = "sample_dashcam.mp4"  # Replace with your video
    output_path = "analysis_results.json"
    
    if not os.path.exists(video_path):
        print(f"Please place a video file at: {video_path}")
        return
    
    from run_analysis import VideoAnalysisRunner
    
    # Run analysis with visualization
    runner = VideoAnalysisRunner(
        video_path=video_path,
        output_path=output_path,
        visualize=True,  # Show real-time visualization
        fps=20.0
    )
    
    success = runner.run()
    
    if success:
        print(f"Analysis completed! Results saved to: {output_path}")
    else:
        print("Analysis failed!")

def example_batch_processing():
    """Example: Batch process multiple videos"""
    print("=== Batch Processing Example ===")
    
    input_dir = "dashcam_videos"  # Directory with video files
    output_dir = "analysis_results"  # Output directory
    
    if not os.path.exists(input_dir):
        print(f"Please create directory with videos: {input_dir}")
        return
    
    from batch_analyze import BatchVideoAnalyzer
    
    # Run batch analysis
    analyzer = BatchVideoAnalyzer(
        input_dir=input_dir,
        output_dir=output_dir,
        max_workers=2  # Process 2 videos in parallel
    )
    
    batch_results = analyzer.run_batch_analysis()
    
    # Save batch report
    analyzer.save_batch_report(batch_results, "batch_report.json")

def example_visualization_only():
    """Example: Visualize existing analysis results"""
    print("=== Visualization Only Example ===")
    
    video_path = "sample_dashcam.mp4"
    results_path = "analysis_results.json"
    
    if not os.path.exists(video_path) or not os.path.exists(results_path):
        print("Please ensure both video and results files exist")
        return
    
    import json
    from visualizer import VideoVisualizer
    
    # Load analysis results
    with open(results_path) as f:
        data = json.load(f)
    
    # Create visualizer and save video
    visualizer = VideoVisualizer(video_path)
    visualizer.save_visualization_video(
        "analysis_visualization.mp4", 
        data['frame_analysis']
    )
    
    print("Visualization video created: analysis_visualization.mp4")

def main():
    print("Openpilot Video Analyzer Examples")
    print("=" * 40)
    
    while True:
        print("\nChoose an example:")
        print("1. Single video analysis")
        print("2. Batch processing")
        print("3. Visualization only")
        print("4. Exit")
        
        choice = input("Enter choice (1-4): ").strip()
        
        if choice == "1":
            example_single_video()
        elif choice == "2":
            example_batch_processing()
        elif choice == "3":
            example_visualization_only()
        elif choice == "4":
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main()