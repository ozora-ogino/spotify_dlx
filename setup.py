"""Python setup.py for project_name package"""
import io
import os

from setuptools import find_packages, setup


def read(*paths, **kwargs):
    """Read the contents of a text file safely.
    >>> read("project_name", "VERSION")
    '0.1.0'
    >>> read("README.md")
    ...
    """

    content = ""
    with io.open(
        os.path.join(os.path.dirname(__file__), *paths),
        encoding=kwargs.get("encoding", "utf8"),
    ) as open_file:
        content = open_file.read().strip()
    return content


def take_package_name(name):
    if name.startswith("-e"):
        return name[name.find("=") + 1 : name.rfind("-")]
    else:
        return name.strip()


def read_requirements(path):
    return [line.strip() for line in read(path).split("\n") if not line.startswith(('"', "#", "-", "git+"))]


# def load_requires_from_file(filepath):
#     with open(filepath) as fp:
#         return [take_package_name(pkg_name) for pkg_name in fp.readlines()]


def load_links_from_file(filepath):
    res = []
    with open(filepath) as fp:
        for pkg_name in fp.readlines():
            if pkg_name.startswith("-e"):
                res.append(pkg_name.split(" ")[1])
    return res


setup(
    name="spotify_dlx",
    version=read("spotify_dlx", "VERSION"),
    description="Download songs from Spotify like youtube-dl",
    url="https://github.com/ozora-ogino/spotify_dlx/",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="ozora-ogino",
    packages=find_packages(exclude=["tests", ".github"]),
    install_requires=read_requirements("requirements.txt"),
    dependency_links=load_links_from_file("requirements.txt"),
    entry_points={"console_scripts": ["project_name = project_name.__main__:main"]},
    extras_require={"test": read_requirements("requirements-test.txt")},
)
