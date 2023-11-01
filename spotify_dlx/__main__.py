#!/usr/bin/env python3
#
# Copyright 2021.
# ozora-ogino
# pylint: disable=redefined-builtin

import os
import platform
from argparse import ArgumentParser
from getpass import getpass

from rich import print

from spotify_dlx import SpotifyDLXClient


def _login(client: SpotifyDLXClient) -> None:
    """Handle login for Spotify API.

    Args:
        client(SpotifyDLClient): SpotifyDLClient.
    """

    # Login with cached credential.
    use_credential_file = os.path.isfile("./credentials.json")
    if use_credential_file:
        print("Credentials are loaded from cache:sparkles:")
        client.login(use_credential_file=use_credential_file)

    # Login with env vars.
    elif "SPOTIFY_USERNAME" in os.environ.keys() and "SPOTIFY_PASSWORD" in os.environ.keys():
        print("Credentials are loaded from env vars:sparkles:")
        username = os.getenv("SPOTIFY_USERNAME")
        password = os.getenv("SPOTIFY_PASSWORD")
        client.login(username=username, password=password)

    # Ask user to type username and password.
    else:
        print("login")
        username = input("Username: ")
        password = getpass()
        client.login(username, password)


def _main():
    parser = ArgumentParser()
    parser.add_argument("--root", default="~/spotify_dlx/songs/")
    parser.add_argument("--root-podcast", default="~/spotify_dlx/podcasts/")
    parser.add_argument("--url")
    parser.add_argument("--disable-skip", default=False, action="store_true")
    parser.add_argument("--liked", default=False, action="store_true")
    parser.add_argument("--playlist", default=False, action="store_true")
    parser.add_argument("--format", default="mp3", choices=["mp3", "wav"])
    parser.add_argument("--limit", default=10, type=int)
    args = parser.parse_args()

    # Clear terminal window.
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")
    print("\n\n")
    print(
        """[green]
            ███████╗██████╗  ██████╗ ████████╗██╗███████╗██╗   ██╗    ██████╗ ██╗     ██╗  ██╗
            ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝██║██╔════╝╚██╗ ██╔╝    ██╔══██╗██║     ╚██╗██╔╝
            ███████╗██████╔╝██║   ██║   ██║   ██║█████╗   ╚████╔╝     ██║  ██║██║      ╚███╔╝
            ╚════██║██╔═══╝ ██║   ██║   ██║   ██║██╔══╝    ╚██╔╝      ██║  ██║██║      ██╔██╗
            ███████║██║     ╚██████╔╝   ██║   ██║██║        ██║       ██████╔╝███████╗██╔╝ ██╗
            ╚══════╝╚═╝      ╚═════╝    ╚═╝   ╚═╝╚═╝        ╚═╝       ╚═════╝ ╚══════╝╚═╝  ╚═╝
            [/green]
        """
    )

    # Initialize Client.
    client = SpotifyDLXClient(**vars(args))
    _login(client)

    if args.playlist:
        print()

        client.download_from_user_playlist()

    elif args.liked:
        print()

        client.download_all_liked_songs()

    elif args.url:
        client.download_from_url(args.url)

    else:
        print(":mag_right:", end="")
        search_query = input("Enter search: ")
        print()
        client.search(search_query, args.limit)


if __name__ == "__main__":
    _main()
