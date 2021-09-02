from flask import Flask, make_response, session, redirect, request, jsonify, render_template
import requests
import os
import random as rand
import string
import pitchfork_api

app = Flask(__name__)
env_config = os.getenv("APP_SETTINGS", "config.DevelopmentConfig")
app.config.from_object(env_config)

def getPrettyDuration(duration):
	if duration == "short_term":
		return "Past 2 Weeks"
	if duration == "medium_term":
		return "Past 6 Months"
	return "All Time"

def makeGetRequest(token, url, params={}):
	headers = {"Authorization": "Bearer {}".format(token)}
	response = requests.get(url, headers=headers, params=params)

	if response.status_code == 200:
		return response.json()

	return None

def getUserInformation(session):
	url = 'https://api.spotify.com/v1/me'
	payload = makeGetRequest(session['token'], url)

	if payload == None:
		return None

	return payload

def getPlaylistInfo(playlist_id, token):
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id
	payload = makeGetRequest(token, url)

	if payload == None:
		return None

	return payload

def getUserPlaylists(session):
	url = 'https://api.spotify.com/v1/me/playlists'
	payload = makeGetRequest(session['token'], url)

	if payload == None:
		return None

	return payload

def getTrackAvgForPlaylist(token, playlist_id):
	print("CHECKING PLAYLIST ID: ", playlist_id)
	url = 'https://api.spotify.com/v1/playlists/' + playlist_id

	# make [a] list of track objs and [b] set of album titles
	track_objs = []
	artist_album_set = set()
	album_score_dict = dict()

	# build track objs and set of albums from spotify
	params = {}
	payload = makeGetRequest(token, url, params)
	for track in payload['tracks']['items']:
		track=track['track']
		track_objs.append(track)
		print("***")
		print(track["album"]["name"])
		artist_album_set.add((track["artists"][0]["name"], track["album"]["name"]))

	print(artist_album_set)
	# check pitchfork
	for item in artist_album_set:
		print("Checking: ", item)
		# add scored albums to dict
		try:
			p = pitchfork_api.search(item[0], item[1])
			print(p.score())
			album_score_dict[item[1]] = p.score()
		except:
			pass

	return track_objs, album_score_dict

def getTrackAvgForDuration(token, time):
	url = 'https://api.spotify.com/v1/me/top/tracks'

	# make [a] list of track objs and [b] set of album titles
	track_objs = []
	artist_album_set = set()
	album_score_dict = dict()

	# build track objs and set of albums from spotify
	params = {'limit': 10, 'time_range': time}
	payload = makeGetRequest(token, url, params)
	for track in payload['items']:
		track_objs.append(track)
		print("***")
		print(track["album"]["name"])
		artist_album_set.add((track["artists"][0]["name"], track["album"]["name"]))

	print(artist_album_set)
	# check pitchfork
	for item in artist_album_set:
		print("Checking: ", item)
		# add scored albums to dict
		try:
			p = pitchfork_api.search(item[0], item[1])
			print(p.score())
			album_score_dict[item[1]] = p.score()
		except:
			pass

	return track_objs, album_score_dict

def getToken(code):
	token_url = 'https://accounts.spotify.com/api/token'
	authorization = app.config['AUTHORIZATION']
	redirect_uri = app.config['REDIRECT_URI']

	headers = {'Authorization': authorization, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
	body = {'code': code, 'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'}
	post_response = requests.post(token_url, headers=headers, data=body)

	print("THE SECOND CALL RESPONSE WAS: ", post_response.status_code)

	# 200 code indicates access token was properly granted
	if post_response.status_code == 200:
		json = post_response.json()
		return json['access_token'], json['refresh_token'], json['expires_in']
	else:
		return None

@app.route('/')
def home():
	return render_template("home.html")

@app.route('/authorize')
def authorize():
	client_id = app.config['CLIENT_ID']
	client_secret = app.config['CLIENT_SECRET']
	redirect_uri = app.config['REDIRECT_URI']
	scope = app.config['SCOPE']

	# redirect user to Spotify authorization page
	authorize_url = 'https://accounts.spotify.com/en/authorize?'
	parameters = 'response_type=code&client_id=' + client_id + '&redirect_uri=' + redirect_uri + '&scope=' + scope
	response = make_response(redirect(authorize_url + parameters))

	return response

@app.route('/callback')
def callback():
	session = dict()
	# check spotify response
	if request.args.get('error'):
		return render_template("home.html")
	else:
		code = request.args.get('code')
		print("THIS IS THE CODE: ", code)

		# get access token to make requests on behalf of the user
		payload = getToken(code)
		if payload != None:
			session['token'] = payload[0]
			session['refresh_token'] = payload[1]
		else:
			return render_template("home.html")

	current_user = getUserInformation(session)
	session['user_id'] = current_user['id']

	playlist_info = getUserPlaylists(session)

	return render_template('pickduration.html', session=session,\
							current_username=current_user['id'],\
							current_userpicture=current_user["images"][0]["url"],
							playlist_info=playlist_info["items"])

@app.route('/review', methods=["POST", "GET"])
def review():
	token = request.args.get('token')
	username = request.args.get('username')
	userpicture = request.args.get('userpicture')
	prettyduration = ""

	# *** HANDLE FORM
	if request.method == "POST":
		print("GOT POST!!")
		# https://open.spotify.com/playlist/1Zvq2VlHEieC5TntEAK3Hb?si=f7ab35cb008f422c
		playlist_id = request.form.get("playlist_url").split("playlist/")[1]
		playlist_info = getPlaylistInfo(playlist_id, token)
		username = playlist_info['owner']['id']
		userpicture = playlist_info['images'][0]['url']
		prettyduration = playlist_info['name']
		track_objs, album_score_dict = getTrackAvgForPlaylist(token, playlist_id)

	# [1] PLAYLIST
	if request.args.get('playlist'):
		playlist_id = request.args.get('playlist')
		playlist_info = getPlaylistInfo(playlist_id, token)
		username = playlist_info['owner']['id']
		userpicture = playlist_info['images'][0]['url']
		prettyduration = playlist_info['name']
		track_objs, album_score_dict = getTrackAvgForPlaylist(token, playlist_id)

	# [2] DURATION
	elif request.args.get('duration'):
		duration = request.args.get('duration')
		prettyduration = getPrettyDuration(duration)
		track_objs, album_score_dict = getTrackAvgForDuration(token, duration)


	# build tracks with their dict scores
	# (track name, track artist, track album, pitchfork score)
	track_response = []
	reviewed_song_count = 0
	tot_rating = 0.0
	for track in track_objs:
		if album_score_dict.get(track["album"]["name"]):
			reviewed_song_count += 1
			tot_rating += album_score_dict.get(track["album"]["name"])
			track_response.append((track["name"],\
									track["artists"][0]["name"],\
									track["album"]["name"],\
									album_score_dict.get(track["album"]["name"])),)
		else:
			track_response.append((track["name"],\
									track["artists"][0]["name"],\
									track["album"]["name"],\
									"n/a"),)

	avg_rating = round(tot_rating/reviewed_song_count, 1)

	return render_template("review.html", track_objs=track_response, avg_rating=avg_rating, prettyduration=prettyduration,\
							current_userpicture=userpicture,current_username=username)
