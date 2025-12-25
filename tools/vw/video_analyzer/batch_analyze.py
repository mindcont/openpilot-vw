#!/usr/bin/env python3
import argparse
import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add openpilot to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from run_analysis import VideoAnalysisRunner

class BatchVideoAnalyzer:
    def __init__(self, input_dir: str, output_dir: str, max_workers: int = 2):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported video formats
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
    
    def find_video_files(self) -> list:
        """Find all video files in input directory"""
        video_files = []
        for ext in self.video_extensions:
            video_files.extend(self.input_dir.glob(f"*{ext}"))
            video_files.extend(self.input_dir.glob(f"*{ext.upper()}"))
        
        return sorted(video_files)
    
    def process_single_video(self, video_path: Path) -> dict:
        """Process a single video file"""
        start_time = time.time()
        
        # Generate output filename
        output_name = video_path.stem + "_analysis.json"
        output_path = self.output_dir / output_name
        
        print(f"Processing: {video_path.name}")
        
        try:
            # Run analysis
            runner = VideoAnalysisRunner(
                str(video_path), 
                str(output_path), 
                visualize=False,  # No visualization in batch mode
                fps=20.0
            )
            
            success = runner.run()
            processing_time = time.time() - start_time
            
            result = {
                'video_file': str(video_path),
                'output_file': str(output_path),
                'success': success,
                'processing_time': processing_time,
                'error': None
            }
            
            if success:
                print(f"✓ Completed: {video_path.name} ({processing_time:.1f}s)")
            else:
                print(f"✗ Failed: {video_path.name}")
                result['error'] = "Analysis failed"
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"✗ Error processing {video_path.name}: {e}")
            
            return {
                'video_file': str(video_path),
                'output_file': str(output_path),
                'success': False,
                'processing_time': processing_time,
                'error': str(e)
            }
    
    def run_batch_analysis(self) -> dict:
        """Run batch analysis on all videos"""
        video_files = self.find_video_files()
        
        if not video_files:
            print(f"No video files found in {self.input_dir}")
            return {'results': [], 'summary': {}}
        
        print(f"Found {len(video_files)} video files")
        print(f"Output directory: {self.output_dir}")
        print(f"Using {self.max_workers} worker threads")
        print("-" * 50)
        
        results = []
        start_time = time.time()
        
        # Process videos in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_video = {
                executor.submit(self.process_single_video, video_path): video_path 
                for video_path in video_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_video):
                result = future.result()
                results.append(result)
        
        total_time = time.time() - start_time
        
        # Generate summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        avg_processing_time = sum(r['processing_time'] for r in results) / len(results)
        
        summary = {
            'total_videos': len(video_files),
            'successful': successful,
            'failed': failed,
            'success_rate': successful / len(video_files),
            'total_processing_time': total_time,
            'average_processing_time': avg_processing_time
        }
        
        print("-" * 50)
        print("=== Batch Analysis Summary ===")
        print(f"Total videos: {summary['total_videos']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success rate: {summary['success_rate']:.1%}")
        print(f"Total time: {summary['total_processing_time']:.1f}s")
        print(f"Average time per video: {summary['average_processing_time']:.1f}s")
        
        return {
            'results': results,
            'summary': summary
        }
    
    def save_batch_report(self, batch_results: dict, report_path: str):
        """Save batch processing report"""
        with open(report_path, 'w') as f:
            json.dump(batch_results, f, indent=2)
        
        print(f"Batch report saved: {report_path}")

def main():
    parser = argparse.ArgumentParser(description='Batch analyze multiple dashcam videos')
    parser.add_argument('--input_dir', required=True, help='Directory containing video files')
    parser.add_argument('--output_dir', required=True, help='Directory for output files')
    parser.add_argument('--workers', type=int, default=2, help='Number of parallel workers (default: 2)')
    parser.add_argument('--report', help='Path to save batch processing report')
    
    args = parser.parse_args()
    
    # Validate input directory
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory not found: {args.input_dir}")
        return 1
    
    # Run batch analysis
    analyzer = BatchVideoAnalyzer(args.input_dir, args.output_dir, args.workers)
    batch_results = analyzer.run_batch_analysis()
    
    # Save report if requested
    if args.report:
        analyzer.save_batch_report(batch_results, args.report)
    
    # Return appropriate exit code
    return 0 if batch_results['summary']['failed'] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())