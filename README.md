# AI Podcast Generator Backend

A FastAPI-based backend service that automatically generates AI-powered podcasts from the latest news using Google AI (Gemini), ElevenLabs TTS, and Supabase for database/storage.

## Features

- **User Authentication**: Signup/login using local bcrypt password hashes and app JWTs
- **AI News Fetching**: Uses Google Search to fetch latest news based on user preferences
- **Script Generation**: Leverages Google Gemini LLM to create natural podcast scripts
- **Text-to-Speech**: Converts scripts to high-quality audio using ElevenLabs
- **Storage**: Saves audio files to Supabase Storage with Firebase fallback
- **Real-time Status**: Track podcast generation progress in real-time

## Tech Stack

- **Backend**: FastAPI + Python 3.9+
- **Authentication**: Local users table + JWT
- **Database**: Supabase PostgreSQL
- **AI Services**: Google AI (Gemini LLM)
- **Text-to-Speech**: ElevenLabs API
- **Storage**: Supabase Storage (primary), Firebase Storage (fallback)
- **HTTP Client**: httpx for async requests

## Project Structure

```
podcast_backend/
├── app/
│   ├── core/
│   │   ├── config.py          # Configuration settings
│   │   └── __init__.py
│   ├── models/
│   │   ├── schemas.py         # Pydantic models
│   │   └── __init__.py
│   ├── routers/
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── podcasts.py       # Podcast endpoints
│   │   └── __init__.py
│   ├── services/
│   │   ├── auth_service.py    # Local authentication and JWTs
│   │   ├── google_ai_service.py # Google AI integration
│   │   ├── elevenlabs_service.py # ElevenLabs TTS
│   │   ├── storage_service.py  # File storage
│   │   ├── podcast_service.py  # Main orchestration
│   │   └── __init__.py
│   └── __init__.py
├── supabase/
│   └── migrations/           # Database migrations
├── main.py                   # FastAPI application
├── requirements.txt          # Python dependencies
├── .env                     # Environment variables
└── README.md
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required environment variables:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key for backend database access
- `JWT_SECRET_KEY`: Secret used to sign app JWTs
- `GOOGLE_API_KEY`: Google AI API key
- `GOOGLE_SEARCH_API_KEY`: Vertex AI Search API key for `searchLite`
- `SEARCH_ENGINE_ID`: Vertex AI Search app/engine ID
- `VERTEX_PROJECT_ID`: Google Cloud project ID that owns the Vertex AI Search app
- `ELEVENLABS_API_KEY`: ElevenLabs API key

### 3. Database Setup

The database tables are already created via Supabase migrations:
- `users`: User profiles, preferences, and bcrypt password hashes
- `podcasts`: Podcast records and metadata
- `generation_logs`: Generation process logs

### 4. Run the Application

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication
- `POST /auth/signup` - Register new user and return JWTs
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user profile
- `PUT /auth/preferences` - Update user preferences

### Podcasts
- `POST /podcasts/generate` - Generate new podcast
- `GET /podcasts/status/{task_id}` - Check generation status
- `GET /podcasts/history` - Get user's podcast history
- `GET /podcasts/{podcast_id}` - Get specific podcast details

### Health Check
- `GET /health` - Health check endpoint

## API Usage Examples

### 1. User Signup
```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "password123",
    "preferences": "technology"
  }'
```
The signup response includes `access_token` and `refresh_token`. Passwords are stored in the `users.password` column as bcrypt hashes, never plaintext.

### 2. User Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "password123"
  }'
```

### 3. Generate Podcast
```bash
curl -X POST "http://localhost:8000/podcasts/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "topic": "artificial intelligence",
    "duration": 5
  }'
```

### 4. Check Generation Status
```bash
curl -X GET "http://localhost:8000/podcasts/status/TASK_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Podcast Generation Process

1. **News Fetching**: Searches for latest news based on user preferences/topic
2. **Script Generation**: Uses Gemini LLM to create natural podcast script
3. **Script Enhancement**: Optimizes script for text-to-speech conversion
4. **Audio Generation**: Converts script to audio using ElevenLabs
5. **Storage Upload**: Saves audio file to Supabase/Firebase storage
6. **Database Update**: Updates podcast record with final results

## Development Notes

- This is a hackathon project focused on functionality over extensive validation
- Error handling and logging are implemented throughout
- All operations are async for better performance
- Background tasks handle podcast generation to avoid blocking requests
- In-memory task tracking (use Redis in production)

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

## Required API Keys

1. **Google AI API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. **Vertex AI Search API Key**: Use a key allowed to call Discovery Engine API (`discoveryengine.googleapis.com`) through `searchLite`
3. **Vertex AI Search App ID**: Put the app/engine ID in `SEARCH_ENGINE_ID`
4. **Vertex AI Search Project ID**: Put the Google Cloud project ID in `VERTEX_PROJECT_ID`
5. **ElevenLabs API Key**: Get from [ElevenLabs](https://elevenlabs.io/)
6. **Supabase Keys**: Available in your Supabase project dashboard

## Storage Configuration

- **Primary**: Supabase Storage (requires creating a "podcasts" bucket)
- **Fallback**: Firebase Storage (optional, requires Firebase credentials)

## Troubleshooting

1. **Database Connection Issues**: Verify Supabase URL and keys
2. **Audio Generation Fails**: Check ElevenLabs API key and quota
3. **Script Generation Issues**: Verify Google AI API key
4. **Storage Upload Fails**: Ensure Supabase storage bucket exists

## License

This project is for educational/hackathon purposes.
