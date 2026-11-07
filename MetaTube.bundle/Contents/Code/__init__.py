# -*- coding: utf-8 -*-

from base64 import urlsafe_b64encode
from random import choice

import utils
from api_client import api
from constants import *
from provider_id import ProviderID
from translator import translate_text

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.agent_kit import Agent, Media  # agent kit
    from plexhints.core_kit import Core  # core kit
    from plexhints.decorator_kit import handler, indirect, route  # decorator kit
    from plexhints.exception_kit import Ex  # exception kit
    from plexhints.locale_kit import Locale  # locale kit
    from plexhints.log_kit import Log  # log kit
    from plexhints.model_kit import Movie, VideoClip, VideoClipObject  # model kit
    from plexhints.network_kit import HTTP  # network kit
    from plexhints.object_kit import Callback, IndirectResponse, MediaObject, MessageContainer, MetadataItem, \
        MetadataSearchResult, PartObject, SearchResult  # object kit
    from plexhints.parse_kit import HTML, JSON, Plist, RSS, XML, YAML  # parse kit
    from plexhints.prefs_kit import Prefs  # prefs kit
    from plexhints.proxy_kit import Proxy  # proxy kit
    from plexhints.resource_kit import Resource  # resource kit
    from plexhints.shortcut_kit import L, E, D, R, S  # shortcut kit
    from plexhints.util_kit import String, Util  # util kit

    from plexhints.constant_kit import CACHE_1MINUTE, CACHE_1HOUR, CACHE_1DAY, CACHE_1WEEK, CACHE_1MONTH  # constant kit
    from plexhints.constant_kit import ClientPlatforms, Protocols, OldProtocols, ServerPlatforms, ViewTypes, \
        SummaryTextTypes, AudioCodecs, VideoCodecs, Containers, ContainerContents, \
        StreamTypes  # constant kit, more commonly used in URL services

    # extra objects
    from plexhints.extras_kit import BehindTheScenesObject, ConcertVideoObject, DeletedSceneObject, FeaturetteObject, \
        InterviewObject, LiveMusicVideoObject, LyricMusicVideoObject, MusicVideoObject, OtherObject, \
        SceneOrSampleObject, ShortObject, TrailerObject


def Start():
    HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1DAY
    HTTP.Headers['Accept-Encoding'] = 'gzip'
    HTTP.Headers['User-Agent'] = DEFAULT_USER_AGENT


def ValidatePrefs():
    Log.Debug('ValidatePrefs called.')


def get_pref(key, default=None):
    """Read a preference without ever raising.

    Plex builds the ``Prefs`` object when the bundle is loaded, so a preference
    that only exists in a newer bundle can be missing at runtime (a plain
    ``Prefs[key]`` then raises KeyError and aborts the whole metadata update).
    Empty values fall back to ``default`` as well, so clearing a text field in
    the UI restores the documented behaviour.
    """
    try:
        value = Prefs[key]
    except Exception:
        Log.Warn('Preference {key} is not available, using {default}'
                 .format(key=key, default=default))
        return default
    return default if value is None or value == '' else value


class MetaTubeAgent(Agent.Movies):
    name = PLUGIN_NAME
    languages = LANGUAGES
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia',
                    'com.plexapp.agents.lambda',
                    'com.plexapp.agents.xbmcnfo']
    contributes_to = ['com.plexapp.agents.none']

    @staticmethod
    def get_rating_image(rating):
        return 'rottentomatoes://image.rating.ripe' \
            if float(rating) >= 6.0 \
            else 'rottentomatoes://image.rating.rotten'

    @staticmethod
    def get_audience_rating_image(rating):
        return 'rottentomatoes://image.rating.upright' \
            if float(rating) >= 6.0 \
            else 'rottentomatoes://image.rating.spilled'

    @staticmethod
    def get_review_image(rating):
        return 'rottentomatoes://image.review.fresh' \
            if not rating or float(rating) >= 6.0 \
            else 'rottentomatoes://image.review.rotten'

    @staticmethod
    def get_actor_image_url(name):

        G_FRIENDS = 'Gfriends'

        try:
            for actor in api.search_actor(q=name, provider=G_FRIENDS, fallback=False):
                if actor.images:
                    return api.get_primary_image_url(provider=G_FRIENDS, id=name,
                                                     url=actor.images[0], ratio=1.0, auto=True)
        except Exception as e:
            Log.Warn('Get actor image error: {name} ({error})'.format(name=name, error=e))

    @staticmethod
    def is_fc2(m):
        # FC2 providers (FC2/FC2DB/FC2PPVDB/fc2hub) never expose a series, so
        # these titles are grouped by provider family or by the FC2-<id>
        # number instead of a series name.
        number = (m.number or '').upper()
        if number.startswith(FC2_NUMBER_PREFIX):
            return True
        provider = (m.provider or '').upper()
        return provider.startswith(FC2_PROVIDER_PREFIX)

    @staticmethod
    def convert_to_real_actor_names(m):

        AV_BASE_SUPPORTED_PROVIDERS = (
            'DUGA',
            'FANZA',
            'GETCHU',
            'MGS',
            'PCOLLE'
        )
        if m.provider.upper() not in AV_BASE_SUPPORTED_PROVIDERS:
            return

        AV_BASE = 'AvBase'

        try:
            results = api.search_movie(q=m.id, provider=AV_BASE)
            if not results:
                Log.Warn('Movie not found on AVBASE: {id}'.format(id=m.id))
            elif len(results) > 1:
                Log.Warn('Multiple movies found on AVBASE: {id}'.format(id=m.id))
            elif results[0].actors:
                m.actors = results[0].actors
        except Exception as e:
            Log.Warn('Convert to real actor names error: {number} ({error})'.format(number=m.number, error=e))

    @staticmethod
    def translate_movie_info(m, lang):
        mode = Prefs[KEY_TRANSLATION_MODE]

        if TRANSLATION_MODE_ENUMS[mode] & \
                TRANSLATION_MODE_ENUMS[TRANSLATION_MODE_TITLE] and m.title:
            m.title = translate_text(m.title, lang=lang, fallback=m.title)

        if TRANSLATION_MODE_ENUMS[mode] & \
                TRANSLATION_MODE_ENUMS[TRANSLATION_MODE_SUMMARY] and m.summary:
            m.summary = translate_text(m.summary, lang=lang, fallback=m.summary)

    @staticmethod
    def translate_reviews(reviews, lang):
        mode = Prefs[KEY_TRANSLATION_MODE]

        if TRANSLATION_MODE_ENUMS[mode] & \
                TRANSLATION_MODE_ENUMS[TRANSLATION_MODE_REVIEWS]:
            for review in reviews:
                if review.comment:
                    review.comment = translate_text(review.comment, lang=lang,
                                                    fallback=review.comment)

    @staticmethod
    def try_update_reviews(pid):
        if not pid.update:
            return

        try:
            return api.get_movie_reviews(provider=pid.provider, id=pid.id,
                                         lazy=(pid.update is not True))
        except Exception as e:
            Log.Warn('Try to update reviews for {pid:s} failed: {error}'
                     .format(pid=pid, error=e))

    def search(self, results, media, lang, manual=False):

        position = None
        search_results = []

        # issued by scanning or auto match
        if (not manual or media.openSubtitlesHash) \
                and media.filename:
            search_results = api.search_movie(
                q=utils.parse_filename_without_ext(media.filename))
        else:
            try:  # exact match by provider and id
                if not media.year or \
                        not isinstance(media.year, str):
                    raise ValueError
                pid = ProviderID.Parse(
                    media.year,  # HACK: use `year` field as pid input
                )
                position = pid.position  # update position
                search_results.append(api.get_movie_info(
                    provider=pid.provider, id=pid.id, lazy=(pid.update is not True)))
                self.try_update_reviews(pid=pid)
            except ValueError:  # fallback to name based search
                search_results = api.search_movie(q=media.name)

        # apply movie provider filter
        if Prefs[KEY_ENABLE_MOVIE_PROVIDER_FILTER]:
            movie_provider_filter = utils.parse_list(Prefs[KEY_MOVIE_PROVIDER_FILTER])
            if movie_provider_filter:
                search_results = [i for i in search_results
                                  if i.provider.upper() in movie_provider_filter]
                search_results.sort(key=lambda i: movie_provider_filter.index(i.provider.upper()))
            else:
                Log.Warn('Movie provider filter enabled but never used')

        if not search_results:
            Log.Warn('Movie not found: {name}'.format(name=media.name))
            return results

        for i, m in enumerate(search_results):
            pid = str(ProviderID(
                provider=m.provider,
                id=m.id,
                position=position,
            ))
            search_result = MetadataSearchResult(
                id=pid,
                name=pid,
                year=(m.release_date.year
                      if m.release_date.year >= 1900 else None),
                score=int(100 - i),
                lang=lang,  # user preferred language
                thumb=api.get_primary_image_url(
                    m.provider, m.id,
                    url=m.thumb_url,
                    pos=1.0, auto=True),
            )
            # HACK: force to add type and summary
            search_result.type = 'movie'
            search_result.summary = DEFAULT_TITLE_TEMPLATE \
                .format(number=m.number, title=m.title)
            results.Append(search_result)

        return results

    def update(self, metadata, media, lang, force=False):

        if force:
            Log.Debug('Force metadata refreshing')

        pid = ProviderID.Parse(metadata.id)
        Log.Info('Get movie info: {0:s}'.format(pid))

        # API Request
        m = api.get_movie_info(provider=pid.provider, id=pid.id)

        original_title = m.title
        release_date = (m.release_date.strftime('%Y-%m-%d')
                        if m.release_date.year >= 1900 else None)

        # Detect Chinese subtitles, poster badge and type tags. All three are
        # derived from file names, so they share one guard: an unreadable file
        # (or a stale module) must never abort the update. Otherwise Plex keeps
        # the "provider:id" fallback title and drops the rest of the metadata.
        chinese_subtitle_on = False
        badge_type = None
        video_files = [p.file for p in utils.extra_media_parts(media)]
        try:
            for filename in video_files:
                if utils.has_chinese_subtitle(filename):
                    chinese_subtitle_on = True
                    Log.Debug('Chinese subtitle detected for {filename}'
                              .format(filename=filename))
                    break

            # Type tags (Plex 类型): 中文字幕 / 无码破解, derived from the same
            # filename rules that pick the poster badge.
            badge_type = utils.get_badge_type_from_files(
                video_files, chinese_subtitle_on)
            if get_pref(KEY_ENABLE_TYPE_TAGS, True):
                if m.genres is None:
                    m.genres = []
                for tag in utils.get_type_tags(
                        badge_type,
                        chinese=get_pref(KEY_TYPE_TAG_CHINESE),
                        uncensored=get_pref(KEY_TYPE_TAG_UNCENSORED),
                        both=get_pref(KEY_TYPE_TAG_CHINESE_UNCENSORED)):
                    m.genres.append(tag)
        except Exception as e:
            Log.Warn('Filename rules failed for {id}: {error}'
                     .format(id=m.id, error=e))

        # Apply Preferences
        if Prefs[KEY_ENABLE_REAL_ACTOR_NAMES]:
            self.convert_to_real_actor_names(m)

        if Prefs[KEY_ENABLE_TITLE_SUBSTITUTION] and Prefs[KEY_TITLE_SUBSTITUTION_TABLE]:
            for k, v in utils.parse_table(Prefs[KEY_TITLE_SUBSTITUTION_TABLE],
                                          sep='\n', b64=True).items():
                m.title = m.title.replace(k, v)

        if Prefs[KEY_ENABLE_ACTOR_SUBSTITUTION] and Prefs[KEY_ACTOR_SUBSTITUTION_TABLE]:
            m.actors = utils.table_substitute(
                utils.parse_table(Prefs[KEY_ACTOR_SUBSTITUTION_TABLE],
                                  sep='\n', b64=True), m.actors)

        if Prefs[KEY_ENABLE_GENRE_SUBSTITUTION] and Prefs[KEY_GENRE_SUBSTITUTION_TABLE]:
            m.genres = utils.table_substitute(
                utils.parse_table(Prefs[KEY_GENRE_SUBSTITUTION_TABLE],
                                  sep='\n', b64=True), m.genres)

        # Translate Info
        if Prefs[KEY_TRANSLATION_MODE] != TRANSLATION_MODE_DISABLED:
            self.translate_movie_info(m, lang=lang)

        # Title
        metadata.title = (Prefs[KEY_TITLE_TEMPLATE]
                          if Prefs[KEY_ENABLE_TITLE_TEMPLATE]
                          else DEFAULT_TITLE_TEMPLATE).format(
            provider=m.provider,
            id=m.id,
            number=m.number,
            title=m.title,
            series=m.series,
            maker=m.maker,
            label=m.label,
            director=m.director,
            actors=(' '.join(m.actors)),
            first_actor=(m.actors[0] if m.actors else ''),
            year=(m.release_date.year if release_date else None),
            date=release_date,
        )

        # Basic Metadata
        metadata.summary = m.summary
        metadata.original_title = original_title

        # Set pid to Tagline
        metadata.tagline = '{pid:s}'.format(pid=pid)

        # Content Rating
        metadata.content_rating = DEFAULT_CONTENT_RATING
        metadata.content_rating_age = DEFAULT_CONTENT_RATING_AGE

        # Producing Country
        metadata.countries.clear()
        metadata.countries.add(DEFAULT_COUNTRY)

        # Studio
        if m.maker.strip():
            metadata.studio = m.maker

        # Release Date
        if m.release_date.year >= 1900:
            metadata.originally_available_at = m.release_date
            metadata.year = m.release_date.year

        # Duration
        if m.runtime:
            metadata.duration = m.runtime * 60 * 1000  # millisecond

        # Clear Ratings
        metadata.rating = 0.0
        metadata.audience_rating = 0.0
        metadata.rating_image = None
        metadata.audience_rating_image = None
        # Clear Reviews
        metadata.reviews.clear()
        # Ratings & Reviews
        if Prefs[KEY_ENABLE_RATINGS] and m.score:
            metadata.rating = m.score * 2.0
            metadata.rating_image = self.get_rating_image(metadata.rating)

            if Prefs[KEY_ENABLE_REVIEWS]:
                try:
                    reviews = api.get_movie_reviews(m.provider, m.id, homepage=m.homepage)
                except Exception as e:
                    Log.Warn('Get reviews for {id} failed {error}'.format(id=m.id, error=e))
                else:
                    if Prefs[KEY_TRANSLATION_MODE] != TRANSLATION_MODE_DISABLED:
                        self.translate_reviews(reviews, lang=lang)
                    for review in reviews:
                        r = metadata.reviews.new()
                        r.author = review.author
                        r.source = m.provider
                        r.image = self.get_review_image(review.score * 2)
                        r.link = m.homepage
                        r.text = review.comment
                        # review.title is intentionally unused; do not assign
                        # it to "_" - RestrictedPython rejects underscore names.

                    # Audience Rating
                    scores = [i.score for i in reviews if i.score > 0]
                    metadata.rating_count = len(scores)
                    metadata.audience_rating = utils.average(scores) * 2
                    metadata.audience_rating_image = self.get_audience_rating_image(metadata.audience_rating)

        # Director
        metadata.directors.clear()
        if Prefs[KEY_ENABLE_DIRECTORS] and m.director:
            director = metadata.directors.new()
            director.name = m.director
            metadata.directors.add(director)

        # Collections
        # Only reset when this update really carries a collection, so a
        # provider without a series cannot wipe collections added by hand
        # (same guard as the cast/roles block below).
        collections = []
        if Prefs[KEY_ENABLE_COLLECTIONS] and m.series.strip():
            collections.append(m.series)
        if Prefs[KEY_ENABLE_FC2_COLLECTION] and self.is_fc2(m) and COLLECTION_FC2 not in collections:
            collections.append(COLLECTION_FC2)
        if collections:
            metadata.collections.clear()
            for collection in collections:
                metadata.collections.add(collection)

        # Genres
        metadata.genres.clear()
        for genre in set(m.genres):
            metadata.genres.add(genre)

        # Tags
        metadata.tags.clear()
        for tag in {m.maker, m.series, m.label}:
            if tag.strip():
                metadata.tags.add(tag)

        # Actors
        # A provider without a cast (amateur / personal-shot titles often
        # have none) must not wipe the cast a previous provider filled in, so
        # only reset when this update really carries names. Iterate the list
        # instead of a set to keep the provider's own cast order.
        if m.actors:
            metadata.roles.clear()
            seen_actors = set()
            for actor in m.actors:
                if not actor or actor in seen_actors:
                    continue
                seen_actors.add(actor)
                role = metadata.roles.new()
                role.name = actor
                role.photo = self.get_actor_image_url(name=actor)

        # Badge (C / U / UC)
        badge = None
        try:
            if get_pref(KEY_ENABLE_BADGES, True):
                badge = utils.get_badge_name_from_type(
                    badge_type,
                    chinese=get_pref(KEY_BADGE_URL, 'zimu.png'),
                    uncensored=get_pref(KEY_BADGE_URL_U, 'u.png'),
                    both=get_pref(KEY_BADGE_URL_UC, 'uc.png'))
                if badge:
                    Log.Debug('Badge detected: {badge}'.format(badge=badge))
        except Exception as e:
            Log.Warn('Badge selection failed: {error}'.format(error=e))

        # Poster Image
        primary = api.get_primary_image_url(m.provider, m.id, pos=pid.position, badge=badge)
        # noinspection PyBroadException
        try:
            content = api.get_content(url=primary)
        except:
            Log.Warn('Failed to download poster image: {primary}'.format(primary=primary))
        else:
            # Do NOT try to clean up older posters here. On PMS 1.40 the
            # poster container is append-only and none of the removal paths
            # work: clear() does not exist, validate_keys() is a no-op,
            # deleting a key only empties the in-memory container, DELETE on
            # /poster returns 404, and metadata.thumb is not writable. Plex
            # also skips a submission whose URL it already knows, so the same
            # key never refreshes the image. Re-submitting the current URL is
            # therefore the only correct behaviour; stale candidates have to
            # be cleaned up from outside by a tool that pins the newest one.
            metadata.posters[primary] = Proxy.Media(content)
            Log.Debug('Poster submitted: {url}'.format(url=primary))

        # Art Image
        backdrop = api.get_backdrop_image_url(m.provider, m.id)
        # noinspection PyBroadException
        try:
            metadata.art[backdrop] = Proxy.Media(api.get_content(url=backdrop))
        except:
            Log.Warn('Failed to load art image: {backdrop}'.format(backdrop=backdrop))

        # Trailer
        trailer_url = (m.preview_video_url or
                       m.preview_video_hls_url)

        if Prefs[KEY_ENABLE_TRAILERS] and trailer_url:
            # Choose thumb for trailer
            if m.preview_images:
                thumb = api.get_thumb_image_url(m.provider, m.id,
                                                url=choice(m.preview_images))
            else:
                thumb = api.get_thumb_image_url(m.provider, m.id)

            trailer = TrailerObject(
                url='{plugin}://trailer/{b64url}'.format(
                    plugin=PLUGIN_NAME.lower(),
                    b64url=urlsafe_b64encode(trailer_url),
                ),
                title=DEFAULT_TRAILER_TEMPLATE.format(
                    number=m.number,
                    title=m.title,
                    original_title=original_title,
                ),
                thumb=thumb,
            )
            metadata.extras.add(trailer)
            Log.Debug('Trailer added: {trailer}'.format(trailer=trailer_url))

        return metadata
