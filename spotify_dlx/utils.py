#!/usr/bin/env python3
#
# Copyright 2021.
# ozora-ogino
# pylint: disable=redefined-builtin
import re
from typing import Any, List, Optional

import music_tag
import requests
from librespot.audio.decoders import AudioQuality
from pydub import AudioSegment


def sanitize_data(value: str) -> str:
    """Returns given string with problematic removed"""
    sanitizes = ["\\", "/", ":", "*", "?", "'", "<", ">", '"']
    for i in sanitizes:
        value = value.replace(i, "")
    return value.replace("|", "-")


# Functions directly related to modifying the downloaded audio and its metadata
def convert_audio_format(filename: str, quality: AudioQuality, format: str) -> None:
    """Converts raw audio into playable mp3 or ogg vorbis"""
    raw_audio = AudioSegment.from_file(filename, format="ogg", frame_rate=44100, channels=2, sample_width=2)
    if quality == AudioQuality.VERY_HIGH:
        bitrate = "320k"
    else:
        bitrate = "160k"
    raw_audio.export(filename, format=format, bitrate=bitrate)


def verify_url_pattern(target: str, url_pattern: str, uri_pattern: str, groupkey: str) -> Optional[str]:
    uri = re.search(uri_pattern, target)
    url = re.search(url_pattern, target)
    if not url and not uri:
        return None
    return (uri if uri is not None else url).group(groupkey)


def _convert_artist_format(artists: List[str]) -> str:
    """Returns converted artist format"""
    formatted = ""
    for x in artists:
        formatted += x + ", "
    return formatted[:-2]


def set_audio_tags(
    filename: str,
    artists: List[str],
    name: str,
    album_name: str,
    release_year: int,
    disc_number: int,
    track_number: int,
):
    """sets music_tag metadata"""
    tags = music_tag.load_file(filename)
    tags["artist"] = _convert_artist_format(artists)
    tags["tracktitle"] = name
    tags["album"] = album_name
    tags["year"] = release_year
    tags["discnumber"] = disc_number
    tags["tracknumber"] = track_number
    tags.save()


def set_music_thumbnail(filename: str, image_url: str):
    """Downloads cover artwork"""
    img = requests.get(image_url).content
    tags = music_tag.load_file(filename)
    tags["artwork"] = img
    tags.save()


def write_wav(filename: str, stream: Any):
    """Save audio as wav file."""
    with open(filename, "wb") as file:
        #  Download the entire track.
        byte = stream.input_stream.stream().read(-1)
        file.write(byte)
