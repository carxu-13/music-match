# music-match

<p align="center">
  <a href="" rel="noopener">
 <img width=200px height=200px src="https://i.imgur.com/6wj0hh6.jpg" alt="project logo"></a>
</p>

<h3 align="center">Music Match</h3>

---

<p align="center"> Visual analysis of cadence data overlaid with music characteristics.
    <br>
</p>

## 📝 Table of Contents
- [About](#about)
- [Getting Started](#getting_started)
- [Usage](#usage)
- [Built Using](#built_using)
- [Authors](#authors)
- [Acknowledgments](#acknowledgement)

## 🧐 About <a name = "about"></a>
I started running in late 2025. This means countless miles spent huffing and puffing, with nothing besides my mind and my music. As I have continued running, I've wondered: Does the music I listen to affect the quality of my running? This project hopes to answer this exact question.

## 🏁 Getting Started <a name = "getting_started"></a>
These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites
- Python 3.10+
- Node.js 18+ (LTS recommended)
- A [Strava API application](https://www.strava.com/settings/api) (Client ID & Secret)
- A [Spotify API application](https://developer.spotify.com/dashboard) (Client ID & Secret, with `http://127.0.0.1:8000/callback` as a redirect URI)
- (Optional) A Garmin Connect account for heart rate data

### Installing

1. **Clone the repository**
```bash
git clone https://github.com/carxu-13/music-match.git
cd music-match
```

2. **Set up the backend**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install flask flask-cors spotipy garminconnect python-dotenv requests numpy
```

3. **Set up the frontend**
```bash
cd frontend
npm install
cd ..
```

4. **Configure environment variables**

Create a `.env` file in the project root:
```
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
GARMIN_EMAIL=your_garmin_email
GARMIN_PASSWORD=your_garmin_password
```

5. **Run the app**

Start the backend and frontend in separate terminals:
```bash
# Terminal 1 — Backend (from project root)
venv\Scripts\activate
cd backend
python server.py
```
```bash
# Terminal 2 — Frontend
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend API at `http://127.0.0.1:8000`.

## 🎈 Usage <a name="usage"></a>
To use this system, you will need to connect your personal Strava account and your personal Spotify account using OAuth 2.0. Additionally, to optionally retrieve HR data, you can connect your Garmin Connect account.

Once connected, select an activity from the list to see an interactive chart showing pace, heart rate, cadence, and song BPM overlaid with your Spotify listening history. A detailed table breaks down metrics per song segment including distance, elevation, and cadence-to-BPM ratio.

**Note:** Spotify only stores the last ~50 recently played tracks (~24 hours). The app caches your listening history locally, so run it regularly to build up history beyond this window.

## ⛏️ Built Using <a name = "built_using"></a>
- [Flask](https://flask.palletsprojects.com/) - Python backend API
- [React](https://react.dev/) - Frontend UI framework
- [Vite](https://vite.dev/) - Frontend build tool
- [Recharts](https://recharts.org/) - Interactive charting library
- [Strava API](https://developers.strava.com/) - Activity data (pace, cadence, elevation)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api) - Listening history
- [Garmin Connect](https://connect.garmin.com/) - Heart rate data (via `garminconnect` library)
- [Deezer API](https://developers.deezer.com/) - Song BPM lookup
- [SQLite](https://www.sqlite.org/) - Local BPM cache

## ✍️ Authors <a name = "authors"></a>
- [@carxu-13](https://github.com/carxu-13) - Idea and Development

## 🎉 Acknowledgements <a name = "acknowledgement"></a>
- [@asatpathy314](https://github.com/asatpathy314) for helping a lot