import os
import sys

try:
    from flask import Flask, render_template, request, jsonify, session
    from googleapiclient.discovery import build
    from summarize import summarize_transcript
    from youtube_transcript_api import YouTubeTranscriptApi
    import yt_dlp
    import re
    import json
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    raise

app = Flask(__name__)

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

# REMOVE session usage - it doesn't work on Vercel serverless
# Delete these lines:
# session['next_page_token'] = ...
# session['prev_page_token'] = ...

# Instead, return tokens to client and pass them back:

@app.route('/search')
def search():
    query = request.args.get('query')
    
    if not query or not query.strip():
        return jsonify({
            'error': 'Search query is required',
            'total_pages': 0,
            'data': []
        }), 400
    
    try:
        result = search_videos(query.strip())
        return jsonify(result)
    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        return jsonify({
            'error': str(e),
            'total_pages': 0,
            'data': []
        }), 500

@app.route('/next')
def next():
    query = request.args.get('query')
    
    try:
        videos = next_page(query)  # No page_token parameter
        return jsonify(videos)
    except Exception as e:
        print(f"Next page error: {e}")
        return jsonify({'error': str(e), 'data': []}), 500

@app.route('/prev')
def prev():
    query = request.args.get('query')
    
    try:
        videos = prev_page(query)  # No page_token parameter
        return jsonify(videos)
    except Exception as e:
        print(f"Prev page error: {e}")
        return jsonify({'error': str(e), 'data': []}), 500

@app.route('/summarize', methods=['GET'])
def summarize():
    video_id = request.args.get('videoId')
    if not video_id:
        return jsonify({"error": "Missing or invalid videoId"}), 400

    transcript = fetch_transcript(video_id)
    if not transcript:
        return jsonify({"error": "Transcript could not be fetched"}), 500

    summary = summarize_transcript(transcript)
    if not summary:
        return jsonify({"error": "Failed to summarize transcript"}, 500)

    return jsonify({"summary": summary})
    

    # except groq.BadRequestError:
        # print('Model context length exceeded.')
        # return jsonify({"error": "Model context length exceeded."}), 400
    # except groq.RateLimitError:
        # print('Rate limit reached for model.')
        # return jsonify({"error": "Rate limit reached for model."}), 400


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

# Set proxy IP address
url = 'https://ip.decodo.com/json'
username = 'spreyxql9i'
password = 'wshQvA4MCk90jck5u='
proxy = f"http://{username}:{password}@us.decodo.com:10000"


def fetch_transcript(video_id):
    if not isinstance(video_id, str) or not video_id.strip():
        raise ValueError("Invalid video ID")
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get subtitles
            subtitles = None
            if 'subtitles' in info and 'en' in info['subtitles']:
                subtitles = info['subtitles']['en']
            elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
                subtitles = info['automatic_captions']['en']
            else:
                raise Exception("No English subtitles found")
            
            # Find the best subtitle format
            subtitle_url = None
            for sub in subtitles:
                if sub.get('ext') in ['json3', 'srv3', 'srv2', 'srv1']:
                    subtitle_url = sub.get('url')
                    break
            
            if not subtitle_url:
                raise Exception("No suitable subtitle format found")
            
            # Download and parse subtitles
            import urllib.request
            import json
            
            response = urllib.request.urlopen(subtitle_url)
            data = json.loads(response.read())
            
            # Extract text from JSON3 format
            transcript_text = ""
            if 'events' in data:
                for event in data['events']:
                    if 'segs' in event:
                        for seg in event['segs']:
                            if 'utf8' in seg:
                                transcript_text += seg['utf8'] + " "
            
            if not transcript_text.strip():
                raise ValueError("Transcript is empty")
            
            return transcript_text.strip()
            
    except Exception as e:
        print(f"yt-dlp error: {e}")
        raise Exception(f"Failed to fetch transcript: {str(e)}")

# Run the test
if __name__ == "__main__":
    app.run()
