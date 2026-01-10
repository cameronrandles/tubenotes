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
    import time
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


# Protect the summarize endpoint (most expensive)
@app.route('/summarize')
@limiter.limit("10 per hour")  # Max 10 summaries per hour per IP
def summarize():
    video_id = request.args.get('videoId')
    
    print(f"=== SUMMARIZE REQUEST ===")
    print(f"Video ID: {video_id}")
    
    if not video_id:
        return jsonify({'error': 'No video ID provided'}), 400
    
    try:
        transcript = fetch_transcript(video_id)
        summary = summarize_transcript(transcript)
        return jsonify({'summary': summary})
        
    except Exception as e:
        import traceback
        print(f"ERROR: {traceback.format_exc()}")
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


# Decodo proxy settings
DECODO_USERNAME = os.environ.get('DECODO_USERNAME')
DECODO_PASSWORD = os.environ.get('DECODO_PASSWORD')
DECODO_HOST = os.environ.get('DECODO_HOST', 'gate.decodo.com')
DECODO_PORT = os.environ.get('DECODO_PORT', '8080')

# Build proxy URL
if DECODO_USERNAME and DECODO_PASSWORD:
    proxy_url = f"http://{DECODO_USERNAME}:{DECODO_PASSWORD}@{DECODO_HOST}:{DECODO_PORT}"
else:
    proxy_url = None

print(f"Proxy configured: {proxy_url[:30] if proxy_url else 'None'}...")


def fetch_transcript(video_id):
    if not isinstance(video_id, str) or not video_id.strip():
        raise ValueError("Invalid video ID")

    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            time.sleep(1)
            
            print(f"Attempt {attempt + 1}: Fetching transcript for {video_id}")
            
            # Try WITHOUT proxy first
            if attempt == 0:
                print("Trying without proxy...")
                transcript_data = YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=['en']
                )
            else:
                # Try WITH proxy second
                print("Trying with proxy...")
                if proxy_url:
                    proxies = {'http': proxy_url, 'https': proxy_url}
                    transcript_data = YouTubeTranscriptApi.get_transcript(
                        video_id,
                        languages=['en'],
                        proxies=proxies
                    )
                else:
                    raise Exception("No proxy configured")
            
            transcript_text = " ".join([entry['text'] for entry in transcript_data])
            
            if not transcript_text.strip():
                raise ValueError("Transcript is empty")
            
            print(f"✓ Success on attempt {attempt + 1}")
            return transcript_text
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
    
    raise Exception("Failed to fetch transcript")


if __name__ == "__main__":
    app.run()
