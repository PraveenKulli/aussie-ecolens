import boto3
import json
import os
import subprocess

s3 = boto3.client('s3')
BUCKET = 'aussie-ecolens-hkri0008'

def lambda_handler(event, context):
    try:
        record = event['Records'][0]['s3']
        bucket = record['bucket']['name']
        key = record['object']['key']

        print(f"Video processing triggered for: {key}")

        # Only process video files in originals/
        if not key.startswith('originals/'):
            return {'statusCode': 200, 'body': 'Skipped'}

        lower_key = key.lower()
        if not any(lower_key.endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']):
            return {'statusCode': 200, 'body': 'Skipped - not a video'}

        filename = os.path.basename(key)
        name_no_ext = os.path.splitext(filename)[0]

        # Download video to /tmp
        local_video = f'/tmp/{filename}'
        s3.download_file(bucket, key, local_video)
        print(f"Downloaded video to {local_video}")

        # Extract 1 frame per second using ffmpeg
        # Assignment requirement: exactly 1 frame per second
        frames_dir = f'/tmp/frames_{name_no_ext}'
        os.makedirs(frames_dir, exist_ok=True)

        ffmpeg_cmd = [
            'ffmpeg', '-i', local_video,
            '-vf', 'fps=1',
            f'{frames_dir}/frame_%04d.jpg',
            '-y'
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        print(f"ffmpeg stdout: {result.stdout}")
        print(f"ffmpeg stderr: {result.stderr}")

        # Upload extracted frames to S3 frames/ folder
        frame_keys = []
        for frame_file in sorted(os.listdir(frames_dir)):
            if frame_file.endswith('.jpg'):
                frame_path = os.path.join(frames_dir, frame_file)
                frame_key = f'frames/{name_no_ext}/{frame_file}'

                with open(frame_path, 'rb') as f:
                    s3.put_object(
                        Bucket=BUCKET,
                        Key=frame_key,
                        Body=f,
                        ContentType='image/jpeg'
                    )
                frame_keys.append(frame_key)
                print(f"Uploaded frame: {frame_key}")

        print(f"Extracted and uploaded {len(frame_keys)} frames")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Extracted {len(frame_keys)} frames',
                'video_key': key,
                'frame_keys': frame_keys
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise e