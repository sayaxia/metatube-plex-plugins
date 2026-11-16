# -*- coding: utf-8 -*-

import utils
from constants import *

try:  # Python 2
    import httplib as http_status
    from urlparse import urljoin
except ImportError:  # Python 3
    from datetime import datetime
    from http import HTTPStatus as http_status
    from urllib.parse import urljoin
finally:
    from requests import Session, PreparedRequest

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.prefs_kit import Prefs  # prefs kit


class BaseInfoObject(object):
    def __init__(self, **data):
        self.id = data['id']  # type: str
        self.provider = data['provider']  # type: str
        self.homepage = data['homepage']  # type: str


class ActorSearchResult(BaseInfoObject):
    def __init__(self, **data):
        super(ActorSearchResult, self).__init__(**data)
        self.name = data['name']  # type: str
        self.images = data['images']  # type: list[str]


class ActorInfoObject(ActorSearchResult):
    def __init__(self, **data):
        super(ActorInfoObject, self).__init__(**data)
        self.aliases = data['aliases']  # type: list[str]
        self.summary = data['summary']  # type: str
        self.hobby = data['hobby']  # type: str
        self.skill = data['skill']  # type: str
        self.height = int(data['height'])  # type: int
        self.cup_size = data['cup_size']  # type: str
        self.blood_type = data['blood_type']  # type: str
        self.measurements = data['measurements']  # type: str
        self.nationality = data['nationality']  # type: str
        self.birthday = utils.parse_date(data['birthday'])  # type: datetime
        self.debut_date = utils.parse_date(data['debut_date'])  # type: datetime


class MovieSearchResult(BaseInfoObject):
    def __init__(self, **data):
        super(MovieSearchResult, self).__init__(**data)
        self.number = data['number']  # type: str
        self.title = data['title']  # type: str
        self.cover_url = data['cover_url']  # type: str
        self.thumb_url = data['thumb_url']  # type: str
        self.score = float(data['score'])  # type: float
        self.actors = data.get('actors', [])  # type: list[str]
        self.release_date = utils.parse_date(data['release_date'])  # type: datetime


class MovieInfoObject(MovieSearchResult):
    def __init__(self, **data):
        super(MovieInfoObject, self).__init__(**data)
        self.summary = data['summary']  # type: str
        self.director = data['director']  # type: str
        self.genres = data['genres']  # type: list[str]
        self.maker = data['maker']  # type: str
        self.label = data['label']  # type: str
        self.series = data['series']  # type: str
        self.runtime = data['runtime']  # type: int
        self.big_cover_url = data['big_cover_url']  # type: str
        self.big_thumb_url = data['big_thumb_url']  # type: str
        self.preview_images = data['preview_images']  # type: list[str]
        self.preview_video_url = data['preview_video_url']  # type: str
        self.preview_video_hls_url = data['preview_video_hls_url']  # type: str


class MovieReviewObject(object):
    def __init__(self, **data):
        self.title = data['title']  # type: str
        self.author = data['author']  # type: str
        self.comment = data['comment']  # type: str
        self.score = float(data['score'])  # type: float
        self.date = utils.parse_date(data['date'])  # type: datetime


class TranslationInfoObject(object):
    def __init__(self, **data):
        self.translated_text = data['translated_text']  # type: str


class APIError(Exception):
    """An API error occurred."""


class APIClient(object):
    ACTOR_INFO_API = '/v1/actors/{0}/{1}'
    MOVIE_INFO_API = '/v1/movies/{0}/{1}'
    MOVIE_REVIEW_API = '/v1/reviews/{0}/{1}'
    ACTOR_SEARCH_API = '/v1/actors/search'
    MOVIE_SEARCH_API = '/v1/movies/search'
    PRIMARY_IMAGE_API = '/v1/images/primary/{0}/{1}'
    THUMB_IMAGE_API = '/v1/images/thumb/{0}/{1}'
    BACKDROP_IMAGE_API = '/v1/images/backdrop/{0}/{1}'
    TRANSLATE_API = '/v1/translate'

    def __init__(self):
        self.session = Session()

    @staticmethod
    def prepare_url(tpl, *paths, **params):
        req = PreparedRequest()
        req.prepare_url(
            url=urljoin(Prefs[KEY_API_SERVER], tpl.format(*paths)),
            params=params)
        return req.url

    def get_content(self, url, headers=None):
        if isinstance(headers, dict):
            headers['User-Agent'] = DEFAULT_USER_AGENT
        with self.session.get(url=url, headers=headers) as r:
            r.raise_for_status()
            return r.content

    def get_json(self, url, require_auth=False):
        headers = {
            'Accept': 'application/json',
            'User-Agent': DEFAULT_USER_AGENT
        }
        if require_auth:
            headers['Authorization'] = 'Bearer {token}'.format(token=Prefs[KEY_API_TOKEN])

        with self.session.get(url=url, headers=headers) as r:
            info = utils.safe_unicode(r.json())
            data = info.get('data')
            error = info.get('error')

            if r.status_code != http_status.OK and error:
                raise APIError('API request error: {0} <{1}>'.format(
                    error['code'], error['message']))
            if not data:
                raise APIError('Response data field is empty')

            return data

    def search_actor(self, q, provider=None, fallback=None):
        return [ActorSearchResult(**data)
                for data in self.get_json(
                url=self.prepare_url(
                    self.ACTOR_SEARCH_API,
                    q=q, provider=provider, fallback=fallback),
                require_auth=True)]

    def search_movie(self, q, provider=None, fallback=None):
        return [MovieSearchResult(**data)
                for data in self.get_json(
                url=self.prepare_url(
                    self.MOVIE_SEARCH_API,
                    q=q, provider=provider, fallback=fallback),
                require_auth=True)]

    def get_actor_info(self, provider, id, lazy=None):
        return ActorInfoObject(**self.get_json(
            url=self.prepare_url(
                self.ACTOR_INFO_API, provider, id,
                lazy=lazy),
            require_auth=True))

    def get_movie_info(self, provider, id, lazy=None):
        return MovieInfoObject(**self.get_json(
            url=self.prepare_url(
                self.MOVIE_INFO_API, provider, id,
                lazy=lazy),
            require_auth=True))

    def get_movie_info_or_fallback(self, provider, id, lazy=None):
        """Fetch movie info, falling back to another provider by number.

        When a provider dies (its module starts answering 500/404) Plex's update
        throws and the item silently reverts to the metadata Plex cached from the
        first scrape - which is the raw Japanese text this fork is meant to
        translate. Looking the same number up on a healthy provider keeps the
        update alive, so nothing is reverted.
        """
        try:
            return self.get_movie_info(provider=provider, id=id, lazy=lazy)
        except APIError as error:
            Log.Warn('Provider {0}:{1} failed ({2}), trying fallback'
                     .format(provider, id, error))
            info = self.fallback_movie_info(provider=provider, id=id)
            if info is None:
                raise error
            return info

    def fallback_movie_info(self, provider, id):
        """Return MovieInfoObject from a healthy provider, or None."""
        number = utils.normalize_number(id)
        try:
            results = self.search_movie(q=number)
        except Exception as error:
            Log.Warn('Fallback search failed for {0}: {1}'
                     .format(number, error))
            return None

        for item in utils.pick_fallback_candidates(results, provider, number):
            try:
                info = self.get_movie_info(provider=item.provider, id=item.id)
            except Exception as error:
                Log.Warn('Fallback provider {0}:{1} failed: {2}'
                         .format(item.provider, item.id, error))
                continue
            Log.Info('Provider fallback: {0}:{1} -> {2}:{3}'
                     .format(provider, id, info.provider, info.id))
            return info

        Log.Warn('No healthy provider for {0} (was {1}:{2})'
                 .format(number, provider, id))
        return None

    def get_movie_reviews(self, provider, id, homepage=None, lazy=None):
        return [MovieReviewObject(**data) for data in self.get_json(
            url=self.prepare_url(
                self.MOVIE_REVIEW_API, provider, id,
                homepage=homepage, lazy=lazy),
            require_auth=True)]

    def get_primary_image_url(self, provider, id,
                              url=None,
                              ratio=None,
                              pos=None,
                              auto=None,
                              badge=None):
        return self.prepare_url(
            self.PRIMARY_IMAGE_API,
            provider, id,
            url=url, ratio=ratio, pos=pos, auto=auto, badge=badge)

    def get_thumb_image_url(self, provider, id, **params):
        return self.prepare_url(
            self.THUMB_IMAGE_API,
            provider, id, **params)

    def get_backdrop_image_url(self, provider, id, **params):
        return self.prepare_url(
            self.BACKDROP_IMAGE_API,
            provider, id, **params)

    def translate(self, q, to, engine, **params):
        return TranslationInfoObject(**self.get_json(
            url=self.prepare_url(
                self.TRANSLATE_API,
                q=q, to=to, engine=engine, **params),
            require_auth=False))


# Export API
api = APIClient()
