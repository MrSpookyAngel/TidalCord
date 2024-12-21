import json
import re
import requests
from urllib.parse import urlparse
from tidalcord.tidalsession import TidalSession
from bs4 import BeautifulSoup, SoupStrainer


class TidalUrl:
    NETLOCS = {"listen.tidal.com", "tidal.com"}
    TRACK_ID_PATTERN = re.compile(r"/(?:album/\d+/)?track/(\d+)")

    def __init__(self, session: TidalSession):
        self.session = session

    def handle_url(self, url: str):
        parsed = urlparse(url)
        track_id = self._extract_track_id(parsed.path)
        if track_id is None:
            return
        return self.session.get_track_info_by_id(track_id)

    @classmethod
    def _extract_track_id(cls, path: str):
        match = cls.TRACK_ID_PATTERN.search(path)
        return match.group(1) if match else None


class YouTubeUrl:
    NETLOCS = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
    TEXT_BRACE_PATTERN = re.compile(r"\s*[\(\[].*?[\)\]]")
    FEAT_PATTERN = re.compile(r"\b(ft\.|feat\.|ft|feat)\b.*$", flags=re.IGNORECASE)
    PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")
    TEXT_BEFORE_2DSPACE_PATTERN = re.compile(r"^(.*?  .*?)(?=  )")
    TEXT_BETWEEN_DSPACE_PATTERN = re.compile(r"(?<=  ).*?(?=  )")

    def __init__(self, session: TidalSession):
        self.session = session

    def handle_url(self, url: str):
        data = self.get_data(url)
        if not data:
            return

        title, artist, album = self.get_track_details(data)
        if title and artist:
            track = self.get_track_by_track_details(title, artist, album)
            if track:
                return track

        title, uploader = self.get_video_details(data)
        if title and uploader:
            track = self.get_track_by_video_details(title, uploader)
            if track:
                return track

    @staticmethod
    def get_data(url):
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
        except requests.RequestException:
            return

        soup = BeautifulSoup(
            response.text, "html.parser", parse_only=SoupStrainer("script")
        )
        script = soup.find("script", string=lambda t: t and "var ytInitialData" in t)
        if not script:
            return

        script_content = script.string.strip()
        start_index = script_content.find("var ytInitialData =") + len(
            "var ytInitialData ="
        )
        json_data = script_content[start_index:].strip(" ;")

        try:
            return json.loads(json_data)
        except json.JSONDecodeError:
            return

    @staticmethod
    def get_video_details(data):
        try:
            video_details = data["playerOverlays"]["playerOverlayRenderer"][
                "videoDetails"
            ]["playerOverlayVideoDetailsRenderer"]
            title = video_details["title"]["simpleText"].lower()
            uploader = video_details["subtitle"]["runs"][0]["text"].lower()
            return title, uploader
        except (KeyError, TypeError):
            return None, None

    @staticmethod
    def get_track_details(data):
        try:
            engagement_panels = data["engagementPanels"]
        except KeyError:
            return None, None, None

        for panel in engagement_panels:
            try:
                track_credits = panel["engagementPanelSectionListRenderer"]["content"][
                    "structuredDescriptionContentRenderer"
                ]["items"][2]["horizontalCardListRenderer"]["cards"][0][
                    "videoAttributeViewModel"
                ]
                title = track_credits["title"].lower()
                artist = track_credits["subtitle"].lower()
                album = track_credits["secondarySubtitle"]["content"].lower()
                return title, artist, album
            except (KeyError, IndexError, TypeError):
                continue
        return None, None, None

    def get_track_by_video_details(self, title: str, uploader: str):
        clean_title = self._clean_title(title)
        queries = [
            clean_title,
            f"{uploader} {clean_title}",
            title,
            f"{uploader} {title}",
        ]

        track = self.session.get_track_info_by_track_details(title, uploader)
        if track:
            return track

        refined_title = self._refine_title_v1(clean_title) or clean_title
        try:
            artist, refined_title = refined_title.split("  ", 1)
            track = self.session.get_track_info_by_track_details(refined_title, artist)
            if track:
                return track
        except ValueError:
            pass

        for refiner in [self._refine_title_v1, self._refine_title_v2]:
            refined_title = refiner(clean_title)
            if refined_title:
                queries.insert(0, f"{uploader} {refined_title}")
                queries.insert(0, refined_title)

        for query in queries:
            track = self._search_track(query)
            if track:
                return track

    def get_track_by_track_details(self, title: str, artist: str, album: str):
        return self.session.get_track_info_by_track_details(title, artist, album)

    @classmethod
    def _clean_title(cls, text: str):
        text = cls.FEAT_PATTERN.sub("", text)
        text = cls.TEXT_BRACE_PATTERN.sub("", text)
        text = cls.PUNCTUATION_PATTERN.sub("", text)
        return text.strip()

    @classmethod
    def _refine_title_v1(cls, text: str):
        match = cls.TEXT_BEFORE_2DSPACE_PATTERN.search(text)
        return match.group(1).strip() if match else None

    @classmethod
    def _refine_title_v2(cls, text: str):
        match = cls.TEXT_BETWEEN_DSPACE_PATTERN.search(text)
        return match.group(0).strip() if match else None

    def _search_track(self, query: str):
        tracks = self.session.search_tracks(query, limit=1)
        return tracks[0] if tracks else None


class UrlHandler:
    def __init__(self, session: TidalSession):
        self.handlers = [
            TidalUrl(session),
            YouTubeUrl(session),
        ]

    def __call__(self, url: str):
        parsed = urlparse(url)
        for handler in self.handlers:
            if parsed.netloc in handler.NETLOCS:
                return handler.handle_url(url)
        raise ValueError(f"No handler found for URL: {url}")
