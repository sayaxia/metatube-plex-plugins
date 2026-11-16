# -*- coding: utf-8 -*-
import json
import os
import threading
import time

import utils
from api_client import api
from constants import *

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.locale_kit import Locale  # locale kit
    from plexhints.log_kit import Log  # log kit
    from plexhints.prefs_kit import Prefs  # prefs kit

TRANSLATOR_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Translation memory
#
# The plug-in cannot read the Chinese text that Plex already shows: update()
# always starts from a fresh metadata object, so "do not overwrite the existing
# Chinese with the Japanese original" cannot be implemented by comparison. The
# memory below is the equivalent guarantee - once a field has been translated
# successfully, that text is reused whenever the engines are unreachable, so a
# quota outage can no longer rewrite the library back to Japanese.
# ---------------------------------------------------------------------------
TM_NAME = 'translation_memory.json'
TM_LLM_NAME = 'translation_llm_usage.json'
TM_LIMIT = 4000
TM_TEXT_LIMIT = 800
TM_FLUSH_INTERVAL = 20.0

# Genre memory: the Chinese genre set last written for a movie number. Genres
# reach the plug-in in Japanese, and a movie whose provider died can come back
# with labels the substitution table has never seen - those used to be written
# straight into Plex. The memory is what the item had before, so an unusable
# batch can be replaced by the known Chinese set instead of raw Japanese.
GM_NAME = 'genre_memory.json'
GM_LIMIT = 5000
GM_LABEL_LIMIT = 40

# Metadata memory: the last Chinese title / summary / genres actually written.
# When every provider is down, update() used to throw and Plex restored the
# first-scrape metadata (raw Japanese). Replaying this entry keeps the Chinese
# text instead - the real last line of defence.
MM_NAME = 'metadata_memory.json'
MM_LIMIT = 5000
MM_SUMMARY_LIMIT = 2000

# The large-model pool is a one-off quota that does not refill, so it is spent
# deliberately: only on a polluted short title, and only up to the budget.
LLM_SOURCE_CHARS = 120

TM = {
    'loaded': False,
    'enabled': False,
    'storage': None,
    'path': None,
    'data': {},
    'dirty': 0,
    'last': 0.0,
}

LLM = {
    'loaded': False,
    'used': 0,
}

GM = {
    'loaded': False,
    'enabled': False,
    'storage': None,
    'path': None,
    'data': {},
}

MM = {
    'loaded': False,
    'enabled': False,
    'storage': None,
    'path': None,
    'data': {},
}


def plugin_storage():
    """Return Plex's ``Core.storage``, or ``None`` when running outside Plex."""
    try:
        core = Core  # injected into the sandbox by the Plex framework
    except NameError:
        return None
    except Exception:
        return None
    try:
        return core.storage
    except Exception:
        return None


def storage_path(storage, name):
    """Resolve a writable path for a data file managed by ``Core.storage``."""
    try:
        return storage.data_item_path(name)
    except Exception:
        pass
    try:
        return os.path.join(Core.app_support_path, name)
    except Exception:
        return None


def storage_read(storage, path):
    if not path:
        return None
    try:
        raw = storage.load(path)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        Log.Warn('Stored data is unreadable, starting from scratch: {path}'
                 .format(path=path))
        return None


def storage_write(storage, path, data):
    try:
        storage.save(path, json.dumps(data))
        return True
    except Exception as e:
        Log.Warn('Cannot persist {path}: {error}'.format(path=path, error=e))
        return False


def tm_ready():
    """Load the memory once per process; False means "run without it"."""
    if TM['loaded']:
        return TM['enabled']
    TM['loaded'] = True

    storage = plugin_storage()
    if storage is None:
        Log.Warn('Translation memory unavailable outside Plex, continuing without it')
        return False

    path = storage_path(storage, TM_NAME)
    if not path:
        Log.Warn('Translation memory has no writable path, continuing without it')
        return False

    TM['storage'] = storage
    TM['path'] = path
    data = storage_read(storage, path)
    if isinstance(data, dict):
        TM['data'] = data
    TM['enabled'] = True
    Log.Info('Translation memory loaded: {count} entries'
             .format(count=len(TM['data'])))
    return True


def tm_get(key):
    if not key or not tm_ready():
        return None
    value = TM['data'].get(key)
    if not value:
        return None
    ok, reason = utils.looks_translated(value)
    if not ok:
        Log.Warn('Translation memory entry rejected for {key}: {reason}'
                 .format(key=key, reason=reason))
        TM['data'].pop(key, None)
        tm_touch()
        return None
    return value


def tm_put(key, value):
    if not key or not value or not tm_ready():
        return
    if len(value) > TM_TEXT_LIMIT:
        value = value[:TM_TEXT_LIMIT]
    TM['data'][key] = value
    if len(TM['data']) > TM_LIMIT:
        for stale in list(TM['data'])[:TM_LIMIT // 10]:
            TM['data'].pop(stale, None)
        Log.Info('Translation memory trimmed to {count} entries'
                 .format(count=len(TM['data'])))
    tm_touch()


def tm_touch():
    TM['dirty'] = TM['dirty'] + 1
    tm_flush()


def tm_flush(force=False):
    if not TM['enabled'] or not TM['dirty']:
        return
    now = time.time()
    if not force and (now - TM['last']) < TM_FLUSH_INTERVAL:
        return
    if storage_write(TM['storage'], TM['path'], TM['data']):
        TM['dirty'] = 0
        TM['last'] = now


def gm_ready():
    """Load the genre memory once per process; False means "run without it"."""
    if GM['loaded']:
        return GM['enabled']
    GM['loaded'] = True

    storage = plugin_storage()
    if storage is None:
        Log.Warn('Genre memory unavailable outside Plex, continuing without it')
        return False

    path = storage_path(storage, GM_NAME)
    if not path:
        Log.Warn('Genre memory has no writable path, continuing without it')
        return False

    GM['storage'] = storage
    GM['path'] = path
    data = storage_read(storage, path)
    if isinstance(data, dict):
        GM['data'] = data
    GM['enabled'] = True
    Log.Info('Genre memory loaded: {count} movies'
             .format(count=len(GM['data'])))
    return True


def gm_get(number):
    """Chinese genres remembered for this movie number, or None."""
    if not number or not gm_ready():
        return None
    labels = GM['data'].get(number)
    if not labels:
        return None
    for label in labels:
        if utils.genre_needs_translation(label):
            # Written by an older build (or by hand); not trustworthy.
            Log.Warn('Genre memory entry rejected for {number}: {label}'
                     .format(number=number, label=label))
            GM['data'].pop(number, None)
            gm_save()
            return None
    return list(labels)


def gm_put(number, genres):
    """Remember the Chinese genre set written for this movie number."""
    if not number or not genres or not gm_ready():
        return
    labels = []
    count = 0
    for genre in genres:
        labels.append(genre)
        count = count + 1
        if count >= GM_LABEL_LIMIT:
            break
    GM['data'][number] = labels
    if len(GM['data']) > GM_LIMIT:
        for stale in list(GM['data'])[:GM_LIMIT // 10]:
            GM['data'].pop(stale, None)
        Log.Info('Genre memory trimmed to {count} movies'
                 .format(count=len(GM['data'])))
    gm_save()


def gm_save():
    if not GM['enabled']:
        return
    storage_write(GM['storage'], GM['path'], GM['data'])


def mm_ready():
    """Load the metadata memory once per process; False means "run without it"."""
    if MM['loaded']:
        return MM['enabled']
    MM['loaded'] = True

    storage = plugin_storage()
    if storage is None:
        Log.Warn('Metadata memory unavailable outside Plex, continuing without it')
        return False

    path = storage_path(storage, MM_NAME)
    if not path:
        Log.Warn('Metadata memory has no writable path, continuing without it')
        return False

    MM['storage'] = storage
    MM['path'] = path
    data = storage_read(storage, path)
    if isinstance(data, dict):
        MM['data'] = data
    MM['enabled'] = True
    Log.Info('Metadata memory loaded: {count} movies'
             .format(count=len(MM['data'])))
    return True


def mm_get(number):
    """Last Chinese metadata written for this number, or None."""
    if not number or not mm_ready():
        return None
    entry = MM['data'].get(number)
    if not isinstance(entry, dict) or not entry.get('t'):
        return None
    for label in entry.get('g') or []:
        if utils.genre_needs_translation(label):
            # Written by an older build (or by hand); not trustworthy.
            Log.Warn('Metadata memory entry rejected for {number}: {label}'
                     .format(number=number, label=label))
            MM['data'].pop(number, None)
            mm_save()
            return None
    return entry


def mm_put(number, title, summary, original_title, genres, actors=None, score=0):
    """Remember the Chinese metadata written for this number."""
    if not number or not title or not mm_ready():
        return
    labels = []
    count = 0
    for genre in genres or []:
        labels.append(genre)
        count = count + 1
        if count >= GM_LABEL_LIMIT:
            break
    cast = []
    count = 0
    for actor in actors or []:
        cast.append(actor)
        count = count + 1
        if count >= GM_LABEL_LIMIT:
            break
    MM['data'][number] = {
        't': title,
        's': summary or u'',
        'o': original_title or u'',
        'g': labels,
        'a': cast,
        'r': score or 0,
    }
    if len(MM['data']) > MM_LIMIT:
        for stale in list(MM['data'])[:MM_LIMIT // 10]:
            MM['data'].pop(stale, None)
        Log.Info('Metadata memory trimmed to {count} movies'
                 .format(count=len(MM['data'])))
    mm_save()


def mm_save():
    if not MM['enabled']:
        return
    storage_write(MM['storage'], MM['path'], MM['data'])


def llm_used():
    """Characters already spent from the non-refillable large-model pool."""
    if LLM['loaded']:
        return LLM['used']
    LLM['loaded'] = True

    storage = plugin_storage()
    if storage is not None:
        data = storage_read(storage, storage_path(storage, TM_LLM_NAME))
        if isinstance(data, dict):
            try:
                LLM['used'] = int(data.get('used', 0))
            except Exception:
                LLM['used'] = 0
    return LLM['used']


def llm_spend(chars):
    LLM['used'] = llm_used() + chars
    storage = plugin_storage()
    if storage is not None:
        path = storage_path(storage, TM_LLM_NAME)
        if path:
            storage_write(storage, path, {'used': LLM['used']})


def baidu_llm_switch():
    """Read the BaiduAI model switch; missing prefs mean "off".

    Plex builds ``Prefs`` when the bundle loads, so a bundle that adds the
    switch while an older ``Preferences`` file is still in place raises
    KeyError - never let that break a translation.
    """
    try:
        return Prefs[KEY_TRANSLATION_BAIDU_LLM]
    except Exception:
        Log.Warn('Preference {key} is not available, using machine translation'
                 .format(key=KEY_TRANSLATION_BAIDU_LLM))
        return None


def pref_or(key, default=None):
    """Read a preference that may be missing from an older Preferences file."""
    try:
        return Prefs[key]
    except Exception:
        return default


def llm_budget():
    raw = pref_or(KEY_TRANSLATION_LLM_BUDGET, '0')
    try:
        return int(u'{0}'.format(raw).strip() or 0)
    except Exception:
        return 0


def llm_allowed(text, field, primary_engine, primary_model):
    """Decide whether the non-refillable pool may be used for this field."""
    if field != 'title':
        return False
    if not text or len(text) > LLM_SOURCE_CHARS:
        return False
    if primary_engine and primary_engine.lower() == 'baiduai' \
            and primary_model == 'llm':
        # The primary attempt already used the pool; do not spend twice.
        return False
    budget = llm_budget()
    if budget <= 0:
        return False
    return llm_used() + len(text) <= budget


def follow_up_engines(primary):
    """Engines to try after ``primary`` fails, in the configured order."""
    raw = pref_or(KEY_TRANSLATION_FALLBACK_ENGINES, 'Baidu,DeepL') or ''
    names = []
    for name in utils.split_words(raw):
        if name.lower() != (primary or '').lower():
            names.append(name)
    return names


def engine_parameters(engine, primary, primary_params):
    """Credentials for ``engine``: the main table for the primary engine, the
    shared prefixed table for every follow-up engine."""
    if primary and engine.lower() == primary.lower():
        return dict(primary_params)
    table = utils.parse_table(
        pref_or(KEY_TRANSLATION_FALLBACK_PARAMETERS, '') or '', origin_key=True)
    params = utils.filter_prefixed(table, engine)
    if params:
        return params
    # BaiduAI (AIT) and the classic Baidu API are two pools on one account and
    # share the same appid/key pair, so BaiduAI -> Baidu works without
    # duplicating credentials in the fallback table.
    if engine.lower() == 'baidu' and primary and primary.lower() == 'baiduai':
        params = dict(primary_params)
        params.pop('baidu-model-type', None)
    return params


def baiduai_parameters(primary, primary_params):
    if primary and primary.lower() == 'baiduai':
        params = dict(primary_params)
    else:
        params = engine_parameters('BaiduAI', primary, primary_params)
    params.pop('baidu-model-type', None)
    return params


def request_translation(engine, text, lang, params):
    """One attempt against one engine; returns the raw text or None."""
    # limit translate request rate to 1 rps, matching the previous behaviour.
    time.sleep(1.0)
    try:
        return api.translate(q=text, to=lang, engine=engine,
                             **params).translated_text
    except Exception as e:
        Log.Warn('Translate via {engine} failed: {error}'
                 .format(engine=engine, error=e))
        return None


def try_llm(text, lang, primary, primary_params):
    """Last resort: BaiduAI large model, used only for a polluted title."""
    params = baiduai_parameters(primary, primary_params)
    if not params:
        Log.Warn('BaiduAI large model fallback skipped: no credentials')
        return None

    params['baidu-model-type'] = 'llm'
    result = request_translation('BaiduAI', text, lang, params)
    if not result:
        return None

    ok, reason = utils.looks_translated(result, source=text, target=lang)
    if not ok:
        Log.Warn('BaiduAI large model result rejected ({reason})'
                 .format(reason=reason))
        return None

    llm_spend(len(text))
    Log.Info('BaiduAI large model fallback used: {chars} chars, total {used}/{budget}'
             .format(chars=len(text), used=llm_used(), budget=llm_budget()))
    return result


def translate_text(text, lang, fallback=None, field=None, cache_key=None):
    """Translate ``text`` through the engine chain, then the memory.

    Order of guarantees:
      1. the translation memory (0 requests, survives quota outages);
      2. the primary engine, then the configured follow-up engines;
      3. the large model, but only to rescue a polluted short title;
      4. ``fallback`` (the original text) when everything failed.
    """
    with TRANSLATOR_LOCK:

        if not text:
            Log.Warn('Translation text is empty')
            return fallback

        if Prefs[KEY_TRANSLATION_MODE] == TRANSLATION_MODE_DISABLED:
            Log.Warn('Translation is disabled')
            return fallback

        if lang == Locale.Language.Japanese:
            Log.Warn('Translation not applied to Japanese')
            return fallback

        remembered = tm_get(cache_key)
        if remembered:
            Log.Info('Translation memory hit: {key}'.format(key=cache_key))
            return remembered

        primary = Prefs[KEY_TRANSLATION_ENGINE]
        primary_params = utils.parse_table(
            Prefs[KEY_TRANSLATION_ENGINE_PARAMETERS], origin_key=True)

        forced_lang = primary_params.pop('to', None)
        if forced_lang:
            Log.Info('Force setting translation language from {lang} to {forced_lang}'
                     .format(lang=lang, forced_lang=forced_lang))
            lang = forced_lang

        Log.Info('Translate text to {lang}: {text}'.format(lang=lang, text=text))

        engines = [primary] + follow_up_engines(primary)
        primary_model = None
        polluted = False

        for engine in engines:
            params = engine_parameters(engine, primary, primary_params)
            if engine and engine.lower() == 'baiduai':
                model_type = utils.resolve_model_type(params, baidu_llm_switch())
                if model_type:
                    params['baidu-model-type'] = model_type
                    if engine == primary:
                        primary_model = model_type
                    Log.Info('BaiduAI model type for {engine}: {model}'
                             .format(engine=engine, model=model_type))

            result = request_translation(engine, text, lang, params)
            if not result:
                continue

            ok, reason = utils.looks_translated(result, source=text, target=lang)
            if not ok:
                polluted = True
                Log.Warn('Translate via {engine} rejected: {reason} | {text}'
                         .format(engine=engine, reason=reason, text=result))
                continue

            if reason != 'ok':
                Log.Info('Translate via {engine} accepted with {reason}'
                         .format(engine=engine, reason=reason))
            tm_put(cache_key, result)
            tm_flush()
            return result

        if polluted and llm_allowed(text, field, primary, primary_model):
            rescued = try_llm(text, lang, primary, primary_params)
            if rescued:
                tm_put(cache_key, rescued)
                tm_flush()
                return rescued

        Log.Error('Translation failed for {key}, keeping the original text '
                  '(engines tried: {engines})'
                  .format(key=cache_key or field or 'unknown',
                          engines=', '.join(engines)))
        tm_flush()
        return fallback


def translate_genres(genres, lang, report=None):
    """Filter the provider's genre labels down to the ones safe to write in Plex.

    Genres arrive in Japanese and the substitution table only knows the labels
    it was taught; whatever still carries kana goes through the same engine
    chain and quality gate as the title, cached in the memory by label (genres
    repeat across the whole library, so one translation serves every item).

    A label that stays Japanese or comes back polluted is dropped rather than
    written, and an empty result tells the caller to leave the item's existing
    genres untouched - that is what stops a provider answering in Japanese (or
    a failed refresh) from leaving Japanese labels behind.

    ``report`` (a dict, optional) receives ``dropped`` - how many labels could
    not be converted - so the caller can decide that the batch is unusable.
    """
    result = []
    seen = set()
    dropped = 0

    for genre in genres or []:
        genre = utils.to_text(genre).strip()
        if not genre or genre in seen:
            continue
        seen.add(genre)

        if not utils.genre_needs_translation(genre):
            result.append(genre)
            continue

        if Prefs[KEY_TRANSLATION_MODE] == TRANSLATION_MODE_DISABLED:
            # Translation is off on purpose; the user accepts the original.
            result.append(genre)
            continue

        translated = translate_text(genre, lang=lang, fallback=None,
                                    field='genre',
                                    cache_key='genre:{0}'.format(genre))
        if not translated:
            dropped = dropped + 1
            Log.Warn('Genre dropped, no usable Chinese label: {genre}'
                     .format(genre=genre))
            continue
        result.append(translated)

    if report is not None:
        report['dropped'] = dropped
    return result


def protected_genres(genres, lang, number):
    """Genres to write into Plex, with the genre memory as the last resort.

    A dead provider does not answer with nothing - it answers with raw
    Japanese labels, and the ones the substitution table has never seen used to
    land in Plex as-is, which is what "the genres went back to Japanese after a
    refresh" looks like. When part of the batch cannot be converted, the set
    remembered for this movie number (already Chinese) wins instead.
    """
    report = {'dropped': 0}
    labels = translate_genres(genres, lang, report)

    if Prefs[KEY_TRANSLATION_MODE] == TRANSLATION_MODE_DISABLED:
        return labels

    remembered = gm_get(number)
    if remembered:
        lost = []
        for old in remembered:
            if old not in labels:
                lost.append(old)
        if not labels or report['dropped'] > 0 or lost:
            Log.Warn('Genres restored from memory for {number}: '
                     '{dropped} unusable, {lost} missing label(s)'
                     .format(number=number, dropped=report['dropped'],
                             lost=len(lost)))
            return remembered

    if labels:
        gm_put(number, labels)
    return labels
