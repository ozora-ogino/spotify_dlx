#!/usr/bin/env python3
#
# Copyright 2021.
# ozora-ogino
# pylint: disable=redefined-builtin,unused-argument,bare-except,raise-missing-from

import json
import os
import os.path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
from librespot.core import Session
from librespot.metadata import EpisodeId, TrackId
from rich import print
from yaspin import yaspin

from spotify_dlx.utils import (
    convert_audio_format,
    sanitize_data,
    set_audio_tags,
    set_music_thumbnail,
    verify_url_pattern,
    write_wav,
)


class SpotifyDLXClient(object):
    def __init__(
        self,
        root: str,
        root_podcast: str,
        disable_skip: bool = False,
        format: str = "mp3",
        **kwargs,
    ):
        """
        Spotify client to download songs, playlists or podcasts.
        This project is inspired by youtube-dl.

        Args: root(str): Root directory to download songs.
              root_podcast(str): Rood directory to download podcast.
              skip(bool): Whether skip exists songs. True for default.
              format(bool): Format type. Currently mp3 and wav (raw) are availabe.

        """
        self.root = root
        self.root_podcast = root_podcast
        self.disable_skip = disable_skip

        # Verify the format.
        if format.lower() not in ["wav", "mp3"]:
            raise ValueError(f"{format} is currently not supported. Select from wav or mp3")
        self.format = format

    def login(
        self,
        username: str = "",
        password: str = "",
        use_credential_file: bool = False,
        return_session: bool = False,
    ) -> Optional[Session]:
        """Login Spotify by username and password.

        Args:
            username (str, optional): Spotify username.
            password (str, optional): Spotify user's password.
            use_credential_file (bool, optional): If true, use cache file. False for default.
            return_session (bool, optional): If true, return session. False for default.

        Returns:
            Optional[Session]: If return_session is true, return the session.
        """
        try:
            if use_credential_file:
                self.session = Session.Builder().stored_file().create()
            else:
                self.session = Session.Builder().user_pass(username, password).create()

            # Setup token and audio quality.
            self.token = self.session.tokens().get("user-read-email")

            # Verify audio quality by membership
            is_premium = self.session.get_user_attribute("type") == "premium"
            self.audio_quality = AudioQuality.VERY_HIGH if is_premium else AudioQuality.HIGH
            return self.session if return_session else None

        except RuntimeError:
            pass

        except:
            print("[red]Failed to login. Check if your username and password is correct.[/red]")
            raise Exception("Credential Error.")

    def download_all_liked_songs(self) -> None:
        """Download all songs liked by specific user."""
        print("[bold green]>>> Downloading from your playlists >>>[/bold green]\n")
        for song in self._fetch_items("https://api.spotify.com/v1/me/tracks"):
            if not song["track"]["name"]:
                print(":dash: Skip: Song does not exit on Spotify anymore.")
            else:
                self.download_track(song["track"]["id"], "Liked Songs/")
            print("\n")

    def download_from_url(self, url: str) -> None:
        """Download songs from URL.

        Args:
            url(str): URL.
        """

        # Verify URL by 4 pattern.
        track_url = verify_url_pattern(
            target=url,
            uri_pattern=r"^spotify:track:(?P<TrackID>[0-9a-zA-Z]{22})$",
            url_pattern=r"^(https?://)?open\.spotify\.com/track/(?P<TrackID>[0-9a-zA-Z]{22})(\?si=.+?)?$",
            groupkey="TrackID",
        )
        album_url = verify_url_pattern(
            target=url,
            uri_pattern=r"^spotify:album:(?P<AlbumID>[0-9a-zA-Z]{22})$",
            url_pattern=r"^(https?://)?open\.spotify\.com/album/(?P<AlbumID>[0-9a-zA-Z]{22})(\?si=.+?)?$",
            groupkey="AlbumID",
        )
        playlist_url = verify_url_pattern(
            target=url,
            uri_pattern=r"^spotify:playlist:(?P<PlaylistID>[0-9a-zA-Z]{22})$",
            url_pattern=r"^(https?://)?open\.spotify\.com/playlist/(?P<PlaylistID>[0-9a-zA-Z]{22})(\?si=.+?)?$",
            groupkey="PlaylistID",
        )
        episode_url = verify_url_pattern(
            target=url,
            uri_pattern=r"^spotify:episode:(?P<EpisodeID>[0-9a-zA-Z]{22})$",
            url_pattern=r"^(https?://)?open\.spotify\.com/episode/(?P<EpisodeID>[0-9a-zA-Z]{22})(\?si=.+?)?$",
            groupkey="PlaylistID",
        )

        if track_url:
            self.download_track(track_url)

        elif album_url:
            self.download_album(album_url)

        elif playlist_url:
            playlist_songs = self._fetch_items(f"https://api.spotify.com/v1/playlists/{playlist_url}/tracks", limit=100)
            playlist_name = self._fetch_playlist_name(playlist_url)
            for song in playlist_songs:
                self.download_track(song["track"]["id"], sanitize_data(playlist_name) + "/")
                print("\n")

        elif episode_url:
            with yaspin(text="Downloading episode", color="yellow") as sppiner:
                self.download_episode(episode_url)
                sppiner.ok("✅")
        else:
            print(f"[red]URL({url}) does not match any pattern.[/red]")

    def download_track(self, track_id_str: str, extra_paths: str = "") -> None:
        """Downloads songs from Spotify by track id.
        Args:
            track_id_str(str): Target track ID.
            extra_paths(str): Optional. This will be used to handle the destination.
        """

        track_id = TrackId.from_base62(track_id_str)
        (
            artists,
            album_name,
            name,
            image_url,
            release_year,
            disc_number,
            track_number,
            song_id,
            is_playable,
        ) = self._fetch_song_info(track_id_str)

        song_name = artists[0] + " - " + name
        base_dir = os.path.join(self.root, extra_paths)
        filename = os.path.join(base_dir, song_name + "." + self.format)

        if not is_playable:
            print(f":dash: Skip: [bold]{song_name}[/bold] is unabailable.")
            return

        if os.path.isfile(filename) and not self.disable_skip:
            print(f":dash:Skip: [bold]{song_name}[/bold] is already exits.")
            return

        if track_id_str != song_id:
            track_id_str = song_id
            track_id = TrackId.from_base62(track_id_str)

        print(f":musical_note: [bold]{song_name}[/bold]")

        with yaspin(text="Downloading", color="yellow") as spinner:
            try:
                stream = self.session.content_feeder().load(
                    track_id, VorbisOnlyAudioQuality(self.audio_quality), False, None
                )

            except:
                spinner.fail("💥")
                print(f":x: Skip: [bold]{song_name}[/bold] cannot be downloaded.")

            else:
                if not os.path.isdir(base_dir):
                    os.makedirs(base_dir)
                write_wav(filename, stream)

                # If target format is not wav, convert data with meta info.
                if self.format != "wav":

                    def _add_tag():
                        """Add tag if converting is completed."""
                        set_audio_tags(
                            filename,
                            artists,
                            name,
                            album_name,
                            release_year,
                            disc_number,
                            track_number,
                        )
                        set_music_thumbnail(filename, image_url)

                    self._convert_wav(
                        filename=filename,
                        quality=self.audio_quality,
                        format=self.format,
                        spinner=spinner,
                        song_name=song_name,
                        # If converting is completed, add meta info.
                        post_processing_func=_add_tag,
                    )

    def _convert_wav(
        self,
        filename: str,
        quality: AudioQuality,
        format: str,
        spinner: Any,
        song_name: str,
        post_processing_func: Callable,
    ) -> None:
        """Conver wav file to target format.

        Args:
            filename(str): Destination.
            quality(AudioQuality): High or VERY_HIGH depends on user's membership.
            format(str): wav or mp3.
            spinner: yaspin's spinner.
            song_name(str): Target's song name.
            post_processing_func: Functions which will be executed after converting.

        """
        try:
            # Convert wav file to target format.
            convert_audio_format(filename, quality, format)
            spinner.ok("✅")
        except:
            os.remove(filename)
            spinner.fail("💥")
            print(
                f":x:Skip: [bold]{song_name}[/bold] could not be converted.",
            )
        else:
            # If converting is completed, add meta info.
            post_processing_func()

    def _fetch_song_info(self, song_id: str) -> Tuple:
        """Fetch song's information which will be used to download.

        Args: song_id(str): Target song's ID

        Returns:
            Tuple: Information which will be used to download and save file with correct information.
        """

        info = json.loads(
            requests.get(
                "https://api.spotify.com/v1/tracks?ids=" + song_id + "&market=from_token",
                headers={"Authorization": "Bearer %s" % self.token},
            ).text
        )

        artists = []
        for data in info["tracks"][0]["artists"]:
            artists.append(sanitize_data(data["name"]))
        album_name = sanitize_data(info["tracks"][0]["album"]["name"])
        name = sanitize_data(info["tracks"][0]["name"])
        image_url = info["tracks"][0]["album"]["images"][0]["url"]
        release_year = info["tracks"][0]["album"]["release_date"].split("-")[0]
        disc_number = info["tracks"][0]["disc_number"]
        track_number = info["tracks"][0]["track_number"]
        scraped_song_id = info["tracks"][0]["id"]
        is_playable = info["tracks"][0]["is_playable"]

        return (
            artists,
            album_name,
            name,
            image_url,
            release_year,
            disc_number,
            track_number,
            scraped_song_id,
            is_playable,
        )

    def download_album(self, album_id: str) -> None:
        """Download songs included in specific album.

        Args:
            album_id(str):Album ID to download.
        """
        artist, album_name = self._fetch_album_info(album_id)
        tracks = self._fetch_items(f"https://api.spotify.com/v1/albums/{album_id}/tracks")
        for track in tracks:
            self.download_track(track["id"], artist + " - " + album_name + "/")
            print("")

    def _fetch_album_info(self, album_id: str) -> Tuple[str, str]:
        """Fetch album info by album_id.

        Args:
            album_id(str): Album ID.
        Returns:
            Tuple[str, str]: Artist name and album name
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"https://api.spotify.com/v1/albums/{album_id}", headers=headers).json()
        return resp["artists"][0]["name"], sanitize_data(resp["name"])

    def download_episode(self, episode_id_str: str) -> None:
        """Download podcast episode by episode id.
        Args:
            episode_id_str(str): Episode ID.
        """
        podcastName, episodeName = self._fetch_episode_info(episode_id_str)
        filename = podcastName + " - " + episodeName + ".wav"
        episode_id = EpisodeId.from_base62(episode_id_str)
        stream = self.session.content_feeder().load(episode_id, VorbisOnlyAudioQuality(self.audio_quality), False, None)

        if not os.path.isdir(self.root_podcast):
            os.makedirs(self.root_podcast)

        with open(self.root_podcast + filename, "wb") as file:
            while True:
                byte = stream.input_stream.stream().read(1024 * 1024)
                if byte == b"":
                    break
                file.write(byte)

    def _fetch_episode_info(self, episode_id: str) -> Tuple[str, str]:
        """Fetch episode name and show name.

        Args:
            episode_id (str): episode id.

        Returns:
            Tuple[str, str]: show name and episode name.
        """

        res = json.loads(
            requests.get(
                "https://api.spotify.com/v1/episodes/" + episode_id,
                headers={"Authorization": "Bearer %s" % self.token},
            ).text
        )

        return res["show"]["name"], res["name"]

    def download_from_user_playlist(self) -> None:
        """Downloads songs from users playlist."""
        # Fetch all playlist of specific user.
        playlists = self._fetch_items("https://api.spotify.com/v1/me/playlists")

        for i, playlist in enumerate(playlists, start=1):
            print(str(i) + ": " + playlist["name"].strip())

        print()
        playlist = input("Select playlist by ID: ")
        print()

        playlist_id = playlists[int(playlist) - 1]["id"]
        print(f"[bold green]>>> Downloading playlist: {playlists[int(playlist) - 1]['name']} >>>[/bold green]\n")

        # Fetch all songs information included in the selected playlist.
        playlist_songs = self._fetch_items(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", limit=100)

        for song in playlist_songs:
            if song["track"]["id"] is not None:
                self.download_track(
                    song["track"]["id"],
                    sanitize_data(playlists[int(playlist) - 1]["name"].strip()) + "/",
                )
            print("\n")

    def _fetch_items(self, url: str, limit: int = 50) -> List[Dict]:
        items = []
        offset = 0

        while True:
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {"limit": limit, "offset": offset}
            res = requests.get(
                url,
                headers=headers,
                params=params,
            ).json()
            offset += limit
            items.extend(res["items"])

            if len(res["items"]) < limit:
                break

        return items

    def fetch_songs_in_playlist(self, playlist_id: str) -> List[Dict]:
        """Fetch a list of songs included in a specific playlist from Spotify API.
           For more details, see below.
           https://developer.spotify.com/console/get-playlist-tracks/

        Args:
            playlist_id(str): ID of playlist to download.
        Returns:
            List[Dict]: List of api response which includes song information.
        """
        songs = []
        offset = 0
        limit = 100

        while True:
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {"limit": limit, "offset": offset}
            res = requests.get(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
                headers=headers,
                params=params,
            ).json()
            offset += limit
            songs.extend(res["items"])

            if len(res["items"]) < limit:
                break

        return songs

    def _fetch_playlist_name(self, playlist_id: str) -> str:
        """
        Fetch playlist information from Spotify API.
        For more details, see below.
        https://developer.spotify.com/console/get-playlist/

        Args:
            playlist_id: ID of playlist.

        Returns:
            str: Playlist name.

        """
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=name,owner(display_name)&market=from_token",
            headers=headers,
        ).json()
        return resp["name"].strip()

    def search(self, search_query: str, limit: int = 10):
        """Searches Spotify's API for relevant data.

        Args:
            search_query(str): Search Query.
            limit(int): Limit of each category to show.
        """

        tracks, albums, playlists = self._fetch_search_info(search_query, limit)

        if len(tracks) + len(albums) + len(playlists) == 0:
            print("No results...")
            return

        # total_tracks = 0
        if len(tracks) > 0:
            print("[magenta bold]Tracks[/magenta bold]")
            for i, track in enumerate(tracks, start=1):
                print(
                    "%d, %s | %s"
                    % (
                        i,
                        track["name"],
                        ",".join([artist["name"] for artist in track["artists"]]),
                    )
                )
            print("\n")

        if len(albums) > 0:
            print("[magenta bold]Albums[/magenta bold]")
            for i, album in enumerate(albums, start=len(tracks) + 1):
                print(
                    "%d, %s | %s"
                    % (
                        i,
                        album["name"],
                        ",".join([artist["name"] for artist in album["artists"]]),
                    )
                )
            print("\n")

        print("[magenta bold]Playlists[/magenta bold]")
        for i, playlist in enumerate(playlists, start=len(tracks) + len(albums) + 1):
            print(
                "%d, %s | %s"
                % (
                    i,
                    playlist["name"],
                    playlist["owner"]["display_name"],
                )
            )
        print("")

        index = int(input("Select by ID: "))
        print("")

        # Downloading single track.
        if index <= len(tracks):
            track_id = tracks[index - 1]["id"]
            self.download_track(track_id)

        # Downloading album.
        elif index <= len(albums) + len(tracks):
            print(f'[bold green]>>> Downloading Album: {albums[index - len(tracks) - 1]["name"]} >>>[/bold green]\n')
            self.download_album(albums[index - len(tracks) - 1]["id"])

        # Downloading playlist.
        else:
            playlist = playlists[index - len(tracks) - len(albums) - 1]
            print(f'[bold green]>>> Downloading Playlist: {playlist["name"]} >>>[/bold green]\n')
            playlist_songs = self._fetch_items(f"https://api.spotify.com/v1/playlists/{playlist['id']}/tracks")
            for song in playlist_songs:
                if song["track"] and song["track"]["id"] is not None:
                    self.download_track(
                        song["track"]["id"],
                        sanitize_data(playlist["name"].strip()) + "/",
                    )
                    print("")

    def _fetch_search_info(self, search_query: str, limit: int = 10) -> Tuple[List]:
        res = requests.get(
            "https://api.spotify.com/v1/search",
            {
                "limit": str(limit),
                "offset": "0",
                "q": search_query,
                "type": "track,album,playlist",
            },
            headers={"Authorization": "Bearer %s" % self.token},
        )

        tracks = res.json()["tracks"]["items"]
        albums = res.json()["albums"]["items"]
        playlists = res.json()["playlists"]["items"]

        return tracks, albums, playlists
