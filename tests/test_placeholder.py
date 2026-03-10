from syncify import get_track, get_playlist
from synciflow.core.youtube import populate_youtube_details_for_track, download_youtube_video_as_mp3

track = get_track("https://open.spotify.com/track/5nJ4Zzqc2UjwSaIcv7bGjx")
print(track.track_title, "-", track.artist_title)
print(track.track_image_url)


youtube_video_id = populate_youtube_details_for_track(track.track_title, track.artist_title)

print(youtube_video_id)

downloaded_path = download_youtube_video_as_mp3(youtube_video_id, "downloads")
print(downloaded_path)

#playlist = get_playlist("https://open.spotify.com/playlist/5YOevUTnavVClJ0hAslu0N")
#print(playlist.title)
#print("Tracks:", len(playlist.track_urls))
#print(playlist.track_urls[:5])
