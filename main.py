import os
import sys

try:
    from flask import Flask, request, jsonify, render_template, session
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from googleapiclient.discovery import build
    from summarize import summarize_transcript
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
    import yt_dlp
    import time
    import urllib.request
    import json
    import re
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    raise

app = Flask(__name__)

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],  # Global limits
    storage_uri="memory://",  # Use memory storage (simple, works on Render)
)

# Get secret key
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')

# Get YouTube API key
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html')


@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms-of-service.html')


@app.route('/videos')
def videos():    
    videos = default_videos()
    return jsonify(videos)


@app.route('/summarize')
@limiter.limit("10 per hour")
def summarize():
    video_id = request.args.get('videoId')
    
    print(f"=== SUMMARIZE REQUEST ===")
    print(f"Video ID: {video_id}")
    
    if not video_id:
        return jsonify({'error': 'No video ID provided'}), 400
    
    try:
        print(f"Step 1: Fetching transcript...")
        transcript = fetch_transcript(video_id)
        print(f"Step 1 SUCCESS: {len(transcript)} chars")
        
        print(f"Step 2: Generating summary...")
        summary = summarize_transcript(transcript)
        
        # DEBUG: Log what we're returning
        print("=" * 60)
        print("SUMMARY DATA:")
        print(type(summary))
        print(summary)
        print("=" * 60)
        
        print(f"Step 2 SUCCESS")
        
        return jsonify({'summary': summary})
        
    except Exception as e:
        import traceback
        print("=" * 60)
        print("ERROR:")
        print(traceback.format_exc())
        print("=" * 60)
        
        return jsonify({'error': str(e)}), 500
    

# Protect search endpoint
@app.route('/search')
@limiter.limit("30 per minute")  # Max 30 searches per minute per IP
def search():
    query = request.args.get('query')
    
    if not query or not query.strip():
        return jsonify({
            'error': 'Search query is required',
            'total_pages': 0,
            'data': []
        }), 400
    
    try:
        videos = search_videos(query.strip())
        return jsonify(videos)
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({
            'error': str(e),
            'total_pages': 0,
            'data': []
        }), 500
    

# Lighter limits for pagination
@app.route('/next')
@limiter.limit("60 per minute")
def next():
    query = request.args.get('query')
    try:
        videos = next_page(query)
        return jsonify(videos)
    except Exception as e:
        return jsonify({'error': str(e), 'data': []}), 500
    

@app.route('/prev')
@limiter.limit("60 per minute")
def prev():
    query = request.args.get('query')
    try:
        videos = prev_page(query)
        return jsonify(videos)
    except Exception as e:
        return jsonify({'error': str(e), 'data': []}), 500
    
    
@app.errorhandler(429)
def ratelimit_handler(e):
    """Custom response when rate limit is exceeded"""
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'You have made too many requests. Please try again later.',
        'retry_after': e.description
    }), 429


def default_videos():
    request = youtube.videos().list(
        part='snippet, statistics',
        chart='mostPopular',
        maxResults=50,
        regionCode='US'
    )
    response = request.execute()

    set_page_tokens(response)

    videos = []
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if not video_id:
            continue  # Skip entries without a valid video ID

        video_data = {
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'video_id': video_id,
            'channel': item['snippet']['channelTitle'],
            'views': item['statistics'].get('viewCount', '0'),
            'postDate': item['snippet']['publishedAt']
        }
        videos.append(video_data)


    total_pages = response['pageInfo']['totalResults'] // response['pageInfo']['resultsPerPage']
    
    return {'total_pages': total_pages, 'data': videos}


def search_videos(query):
    request = youtube.search().list(
        part='snippet',
        q=query,
        relevanceLanguage='en',
        maxResults=50,
        type='video',
        # videoCaption='closedCaption',
        regionCode='US'
    )
    
    response = request.execute()

    set_page_tokens(response)

    videos = []
    video_ids = []
    
    # First, collect all video IDs
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if video_id:
            video_ids.append(video_id)
    
    # Fetch statistics (views, likes, etc.) for all videos in one API call
    stats_response = {}
    if video_ids:
        try:
            stats_request = youtube.videos().list(
                part='statistics',
                id=','.join(video_ids)
            )
            stats_data = stats_request.execute()
            
            # Create a dictionary mapping video_id to statistics
            for video in stats_data.get('items', []):
                stats_response[video['id']] = video.get('statistics', {})
        except Exception as e:
            print(f"Error fetching video statistics: {e}")
    
    # Now build the video data with statistics
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if not video_id:
            continue  # Skip entries without a valid video ID

        # Get statistics for this video
        stats = stats_response.get(video_id, {})
        view_count = stats.get('viewCount', '0')
        
        video_data = {
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'video_id': video_id,
            'channel': item['snippet']['channelTitle'],
            'postDate': item['snippet']['publishedAt'],
            'views': int(view_count) if view_count.isdigit() else 0
        }
        videos.append(video_data)

    # Safe division - handle edge cases
    results_per_page = response['pageInfo'].get('resultsPerPage', 1)
    total_results = response['pageInfo'].get('totalResults', 0)
    
    total_pages = total_results // results_per_page if results_per_page > 0 else 0

    return {'total_pages': total_pages, 'data': videos}


def next_page(query=None):
    if query:
        request = youtube.search().list(
            part='snippet',
            q=query,
            relevanceLanguage='en',
            maxResults=50,
            pageToken=session.get('next_page_token'),  # FROM SESSION
            type='video',
            regionCode='US'
        )
    else:
        request = youtube.videos().list(
            part='snippet,statistics',
            chart='mostPopular',
            maxResults=50,
            pageToken=session.get('next_page_token'),  # FROM SESSION
            regionCode='US'
        )

    response = request.execute()
    set_page_tokens(response)  # SAVE TO SESSION
    
    videos = []
    video_ids = []
    
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if video_id:
            video_ids.append(video_id)
    
    # Fetch statistics
    stats_response = {}
    if video_ids:
        try:
            stats_request = youtube.videos().list(
                part='statistics',
                id=','.join(video_ids)
            )
            stats_data = stats_request.execute()
            
            for video in stats_data.get('items', []):
                stats_response[video['id']] = video.get('statistics', {})
        except Exception as e:
            print(f"Error fetching statistics: {e}")
    
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if not video_id:
            continue

        stats = stats_response.get(video_id, {})
        view_count = stats.get('viewCount', '0')

        video_data = {
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'video_id': video_id,
            'channel': item['snippet']['channelTitle'],
            'postDate': item['snippet']['publishedAt'],
            'views': int(view_count) if view_count.isdigit() else 0
        }
        videos.append(video_data)

    results_per_page = response['pageInfo'].get('resultsPerPage', 1)
    total_results = response['pageInfo'].get('totalResults', 0)
    total_pages = total_results // results_per_page if results_per_page > 0 else 0
    
    return {'total_pages': total_pages, 'data': videos}


def prev_page(query=None):
    if query:
        request = youtube.search().list(
            part='snippet',
            q=query,
            relevanceLanguage='en',
            maxResults=50,
            pageToken=session.get('prev_page_token'),  # FROM SESSION
            type='video',
            regionCode='US'
        )
    else:
        request = youtube.videos().list(
            part='snippet,statistics',
            chart='mostPopular',
            maxResults=50,
            pageToken=session.get('prev_page_token'),  # FROM SESSION
            regionCode='US'
        )

    response = request.execute()
    set_page_tokens(response)  # SAVE TO SESSION
    
    videos = []
    video_ids = []
    
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if video_id:
            video_ids.append(video_id)
    
    stats_response = {}
    if video_ids:
        try:
            stats_request = youtube.videos().list(
                part='statistics',
                id=','.join(video_ids)
            )
            stats_data = stats_request.execute()
            
            for video in stats_data.get('items', []):
                stats_response[video['id']] = video.get('statistics', {})
        except Exception as e:
            print(f"Error fetching statistics: {e}")
    
    for item in response['items']:
        video_id = item['id']['videoId'] if isinstance(item['id'], dict) and 'videoId' in item['id'] else item['id']
        if not video_id:
            continue

        stats = stats_response.get(video_id, {})
        view_count = stats.get('viewCount', '0')

        video_data = {
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['high']['url'],
            'video_id': video_id,
            'channel': item['snippet']['channelTitle'],
            'postDate': item['snippet']['publishedAt'],
            'views': int(view_count) if view_count.isdigit() else 0
        }
        videos.append(video_data)

    results_per_page = response['pageInfo'].get('resultsPerPage', 1)
    total_results = response['pageInfo'].get('totalResults', 0)
    total_pages = total_results // results_per_page if results_per_page > 0 else 0
    
    return {'total_pages': total_pages, 'data': videos}


def set_page_tokens(response):
    """Store tokens in session"""
    session['next_page_token'] = response.get('nextPageToken')
    session['prev_page_token'] = response.get('prevPageToken')


# Store credentials only
DECODO_USERNAME = os.environ.get('DECODO_USERNAME')
DECODO_PASSWORD = os.environ.get('DECODO_PASSWORD')
DECODO_HOST = os.environ.get('DECODO_HOST', 'us.decodo.com')
DECODO_PORT = os.environ.get('DECODO_PORT', '10001')

# Build proxy URL (GLOBAL)
if DECODO_USERNAME and DECODO_PASSWORD:
    proxy_url = f"http://{DECODO_USERNAME}:{DECODO_PASSWORD}@{DECODO_HOST}:{DECODO_PORT}"
    print(f"✓ Proxy configured: {proxy_url[:30]}...")
else:
    proxy_url = None
    print("⚠ No proxy configured")


def fetch_transcript(video_id, proxy=None):
    if not isinstance(video_id, str) or not video_id.strip():
        raise ValueError("Invalid video ID")

    # Use passed proxy or fall back to global
    if proxy is None:
        proxy = proxy_url  # Use global if not passed
    
    errors = []
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Method 1: yt-dlp with proxy
    try:
        print(f"Method 1: yt-dlp")
        
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
        }
        
        # Use the proxy parameter
        if proxy:
            ydl_opts['proxy'] = proxy
            print(f"✓ Using proxy")
        
        # Step 3: Extract video info
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Step 4: Get English subtitles
            subtitles = None
            if 'subtitles' in info and 'en' in info['subtitles']:
                subtitles = info['subtitles']['en']
                print("Found manual English subtitles")
            elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
                subtitles = info['automatic_captions']['en']
                print("Found automatic English captions")
            
            if not subtitles:
                raise Exception("No English subtitles available")
            
            # Step 5: Find best subtitle URL
            subtitle_url = None
            for sub in subtitles:
                ext = sub.get('ext', '')
                if ext in ['json3', 'srv3', 'srv2', 'srv1']:
                    subtitle_url = sub.get('url')
                    print(f"Found subtitle format: {ext}")
                    break
            
            if not subtitle_url and len(subtitles) > 0:
                subtitle_url = subtitles[0].get('url')
                print(f"Using fallback subtitle format: {subtitles[0].get('ext')}")
            
            if not subtitle_url:
                raise Exception("No subtitle URL found")
            
            # Step 6: Download subtitle file
            if proxy_url:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': proxy_url,
                    'https': proxy_url
                })
                opener = urllib.request.build_opener(proxy_handler)
                urllib.request.install_opener(opener)
                print("Using proxy for subtitle download")
            
            req = urllib.request.Request(
                subtitle_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            
            response = urllib.request.urlopen(req, timeout=30)
            content = response.read()
            
            # Step 7: Parse subtitle content
            transcript_text = ""
            
            try:
                # Try JSON3 format
                data = json.loads(content)
                
                if 'events' in data:
                    for event in data['events']:
                        if 'segs' in event:
                            for seg in event['segs']:
                                if 'utf8' in seg:
                                    transcript_text += seg['utf8'] + " "
                
                print("Parsed JSON3 subtitle format")
                                    
            except json.JSONDecodeError:
                # Try VTT/plain text format
                text = content.decode('utf-8', errors='ignore')
                
                # Remove VTT headers and timestamps
                text = re.sub(r'WEBVTT\n', '', text)
                text = re.sub(r'Kind:.*\n', '', text)
                text = re.sub(r'Language:.*\n', '', text)
                text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', '', text)
                text = re.sub(r'\n\d+\n', ' ', text)
                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                text = ' '.join(text.split())
                transcript_text = text
                
                print("Parsed VTT subtitle format")
            
            # Step 8: Validate and return
            if transcript_text.strip():
                print(f"✓ Method 1 SUCCESS: {len(transcript_text)} characters")
                return transcript_text.strip()
            else:
                raise Exception("Parsed transcript is empty")
                
    except Exception as e:
        error = str(e)
        errors.append(f"yt-dlp: {error}")
        print(f"✗ Method 1 FAILED: {error}")
    
    # Method 2: youtube-transcript-api (fallback, simpler but may be blocked)
    try:
        print(f"Method 2: youtube-transcript-api (no proxy)")
        time.sleep(2)  # Rate limiting
        
        transcript_data = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=['en']
        )
        
        transcript_text = " ".join([entry['text'] for entry in transcript_data])
        
        if transcript_text.strip():
            print(f"✓ Method 2 SUCCESS: {len(transcript_text)} characters")
            return transcript_text
            
    except Exception as e:
        error = str(e)
        errors.append(f"youtube-transcript-api: {error}")
        print(f"✗ Method 2 FAILED: {error}")
    
    # Both methods failed - provide helpful error message
    all_errors = " | ".join(errors)
    print(f"=" * 60)
    print(f"ALL METHODS FAILED")
    print(f"Errors: {all_errors}")
    print(f"=" * 60)
    
    # Determine appropriate error message
    if "no subtitles" in all_errors.lower() or "transcripts disabled" in all_errors.lower():
        raise Exception("This video does not have captions available. Please try a different video.")
    elif "unavailable" in all_errors.lower() or "private" in all_errors.lower():
        raise Exception("Video is unavailable or private")
    elif "bot" in all_errors.lower() or "sign in" in all_errors.lower():
        raise Exception("YouTube is blocking requests. Please try again later.")
    else:
        raise Exception("Unable to fetch transcript. The video may not have captions.")
    

if __name__ == "__main__":
    app.run()
