from pathlib import Path
import string

import tidalapi
import tidalapi.exceptions


class TidalSession:
    def __init__(self, session_path: Path, config: tidalapi.Config = tidalapi.Config()):
        self.session = tidalapi.Session(config)
        self.logged_in = self.session.login_session_file(session_path)

    def search_tracks(self, query: str, limit: int = 1):
        results = self.session.search(query, models=[tidalapi.Track], limit=limit)
        return [self._get_track_info(track) for track in results["tracks"]]

    def get_track_info_by_id(self, track_id: str):
        try:
            track = self.session.track(track_id)
        except tidalapi.exceptions.ObjectNotFound:
            return
        return self._get_track_info(track)

    def get_track_info_by_track_details(
        self, title: str, artist: str, album: str = None, limit: int = 10
    ):
        try:
            artist_results = self.session.search(
                artist, models=[tidalapi.Artist], limit=limit
            )["artists"]

            for _artist in artist_results:
                if artist != _artist.name.lower():
                    continue

                albums = (
                    self._get_matching_albums(_artist, album)
                    if album
                    else _artist.get_albums() + _artist.get_ep_singles()
                )

                # Search tracks by full name match
                for _album in albums:
                    for _track in _album.tracks():
                        if title == _track.full_name.lower():
                            return self._get_track_info(_track)

                # Search tracks by partial name match
                for _album in albums:
                    for _track in _album.tracks():
                        if title in _track.name.lower():
                            return self._get_track_info(_track)
        except Exception:
            return

    @staticmethod
    def _get_matching_albums(artist: tidalapi.Artist, album: str):
        albums = [
            _album
            for _album in artist.get_albums()
            if _album.name.lower() == album.lower()
        ]

        if not albums:
            normalized_album = album.translate(
                str.maketrans("", "", string.punctuation)
            ).lower()
            albums = [
                _album
                for _album in artist.get_albums()
                if _album.name.translate(
                    str.maketrans("", "", string.punctuation)
                ).lower()
                == normalized_album
            ]
        return albums

    @staticmethod
    def _get_track_info(track):
        return {
            "id": str(track.id),
            "url": track.get_url(),
            "title": track.full_name,
            "artist": track.artist.name,
            "featured_artists": [
                artist.name
                for artist in track.artists
                if artist.name != track.artist.name
            ],
            "duration": track.duration,
        }
