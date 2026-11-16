# -*- coding: utf-8 -*-
import os
import re
import sys
from base64 import b64decode
from datetime import datetime

from constants import *

try:  # Python 2
    from urllib import unquote
except ImportError:  # Python 3
    from urllib.parse import unquote

# Python 3 compatible code
if sys.version_info.major == 3:
    unicode = str
    # noinspection PyShadowingBuiltins
    filter = lambda f, t: u''.join(i for i in t if f(i))


# Based on an answer by John Machin on Stack Overflow:
# - http://stackoverflow.com/questions/8733233/filtering-out-certain-bytes-in-python
def filter_invalid_xml_chars(s):
    def is_valid_xml_char(i):
        c = ord(i)
        return (0x20 <= c <= 0xD7FF or
                0xE000 <= c <= 0xFFFD or
                0x10000 <= c <= 0x10FFFF or
                c in (0x9, 0xA, 0xD))

    return filter(is_valid_xml_char, s)


def safe_unicode(o):
    if isinstance(o, unicode):
        return filter_invalid_xml_chars(o)
    elif isinstance(o, list):
        return [safe_unicode(v) for v in o]
    elif isinstance(o, dict):
        return dict((k, safe_unicode(v)) for k, v in o.items())
    else:
        return o


def average(a):
    x = 0.0
    if not a:
        return x
    for i in a:
        x = x + i
    return x / len(a)


def parse_filename(filename):
    return os.path.basename(unquote(filename))


def parse_filename_without_ext(filename):
    return os.path.splitext(parse_filename(filename))[0]


def parse_date(s):
    # noinspection PyBroadException
    try:
        return datetime.strptime(
            re.findall(r'\d{4}-\d{2}-\d{2}', s)[0], '%Y-%m-%d')
    except:
        return datetime(1, 1, 1)  # default value


def parse_list(s, sep=','):
    return [i.strip().upper() for i in s.split(sep) if i.strip()]


def parse_table(s, sep=',', b64=False, origin_key=False):
    table = {}
    if not s:
        return table
    if b64:
        s = b64decode(s).decode('utf-8')
    for kv in s.split(sep):
        kv = kv.strip()  # trim all whitespaces
        if kv.count('=') > 0 and not kv.startswith('='):
            i = kv.find('=')
            table[(kv[:i] if origin_key else kv[:i].upper())] = kv[i + 1:]
    return table


def table_substitute(table, items):
    return [(table[i.upper()] if i.upper() in table else i) for i in items]


def resolve_model_type(params, use_llm):
    """Pick the BaiduAI ``model_type`` from the Plex switch.

    BaiduAI exposes two models behind one endpoint: ``nmt`` (machine
    translation, 1M free characters per month for personal-certified
    accounts) and ``llm`` (large-model translation, 1M testing quota).
    The switch only fills in a default: an explicit ``baidu-model-type``
    in the parameter table always wins, so power users keep full control.

    Returns the value to send, or ``None`` when the caller should leave the
    parameter table untouched.
    """
    for key in params:
        if key.lower() == 'baidu-model-type':
            return None
    if '{0}'.format(use_llm).strip().lower() in ('1', 'true', 'yes', 'on'):
        return 'llm'
    return 'nmt'


# Plex runs plug-ins with a trimmed ``builtins``: ``any`` and ``bytes`` are
# both missing there (verified against PMS Plugin Logs, which logged
# "global name 'any' is not defined" and later "global name 'bytes' is not
# defined"). Decide the text/byte types from the interpreter version instead
# of a ``NameError`` probe - the Python 3 shim near the top aliases
# ``unicode`` to ``str``, which would make a probe pick the wrong pair.
#
# The names must NOT start with an underscore: RestrictedPython rejects every
# such identifier at compile time ("_X is an invalid variable name because it
# starts with _") and the whole plug-in fails to load, which makes it vanish
# from Plex entirely. Keep module level helpers underscore-free for the same
# reason.
if sys.version_info.major == 3:
    TEXT_TYPE = str
    BYTE_TYPE = bytes
else:
    TEXT_TYPE = unicode   # noqa: F821  (Python 2; ``str`` is the byte type)
    BYTE_TYPE = str


def as_unicode(value):
    """Best-effort conversion to ``unicode``.

    Plex hands file names over as ``str`` on some endpoints and ``unicode`` on
    others. Mixing the two in Python 2 makes the interpreter decode the byte
    string with ASCII and raise UnicodeDecodeError, so every comparison below
    goes through this helper first.
    """
    if isinstance(value, TEXT_TYPE):
        return value
    if isinstance(value, BYTE_TYPE):
        for encoding in ('utf-8', 'latin-1'):
            try:
                return value.decode(encoding)
            except Exception:
                continue
        return value.decode('utf-8', 'replace')
    return TEXT_TYPE(value)


def probe(func, *args):
    """Run a filesystem probe, treating any failure as "no evidence".

    Scanning a NAS folder can raise (undecodable names, vanished share, ...).
    A probe is only ever a hint, so it must never take down the caller.
    """
    try:
        return func(*args)
    except Exception:
        return False


def has_embedded_chinese_subtitle(video_name):
    def has_tag(s, *tags):
        values = [i.upper() for i in re.split(r'[-_\s]', as_unicode(s))]
        for tag in tags:
            if tag.upper() in values:
                return True
        return False

    name, ext = os.path.splitext(
        os.path.basename(video_name))
    if ext.lower() not in VIDEO_EXTENSIONS:
        return False

    # CHINESE_SUBTITLE is a byte string on Python 2, so comparing it with a
    # unicode name would raise; normalise both sides first.
    return (as_unicode(CHINESE_SUBTITLE) in as_unicode(name) or
            has_tag(name, 'C', 'UC', 'ch'))


def list_dir_names(folder):
    """Filenames in ``folder``, or an empty list when it cannot be read.

    A NFS/CIFS share may hold names that cannot be decoded, or the folder may
    vanish between two scans; neither is worth aborting a metadata update.
    """
    try:
        return os.listdir(folder)
    except Exception:
        return []


def has_external_chinese_subtitle(video_name, *filenames):
    if not filenames:
        if not probe(os.path.exists, video_name):
            return False
        return has_external_chinese_subtitle(
            video_name,
            *list_dir_names(os.path.dirname(video_name) or '.'))

    basename, ext = os.path.splitext(
        os.path.basename(video_name))
    if ext.lower() not in VIDEO_EXTENSIONS:
        return False

    r = re.compile(
        r'\.(ch[ist]|zho?(-(cn|hk|sg|tw))?)\.(ass|srt|ssa|smi|sub|idx|psb|vtt)$', re.IGNORECASE)
    candidates = subtitle_name_candidates(video_name)
    for filename in filenames:
        name = as_unicode(filename)
        if r.search(name) and r.sub('', name).upper() in candidates:
            return True
    return False


def has_chinese_subtitle(video_name):
    # Both probes may touch the filesystem; neither is allowed to raise.
    return (probe(has_embedded_chinese_subtitle, video_name) or
            probe(has_external_chinese_subtitle, video_name))


# Badge types, matching the assets embedded in metatube-sdk-go:
#   zimu.png -> chinese subtitle only
#   u.png    -> uncensored only
#   uc.png   -> chinese subtitle + uncensored
BADGE_TYPE_CHINESE = 'c'
BADGE_TYPE_UNCENSORED = 'u'
BADGE_TYPE_CHINESE_UNCENSORED = 'uc'

# Tags that mark a video as uncensored / mosaic-restored. Besides the explicit
# "-U" suffix, AI mosaic-restoration releases use "-LTX" (and occasionally
# "-BasicVSR++" or "__restored"), which are uncensored by nature.
# "-UNCENSORED" is the spelled out form of the same marker. The separator is
# not significant: "-LTX", "_LTX" and "__restored" all mean the same as "-U".
UNCENSORED_TAGS = ('U', 'UNCENSORED', 'LTX', 'RESTORED',
                   'BASICVSR', 'BASICVSR++')

# Subtitle extensions considered when looking for a bare same-name subtitle.
# Only formats that are unambiguously subtitles: ".txt" is left out on purpose
# because release notes / passwords / magnet links are commonly shipped as
# "ABP-321.txt", and ".idx" is useless without its ".sub" partner (which is
# matched on its own).
BARE_SUBTITLE_EXTENSIONS = ('ass', 'srt', 'ssa', 'smi', 'sub', 'psb', 'vtt')


# Trailing tokens that mark a video as uncensored / subtitled. Used to accept a
# subtitle named after the bare number when the video itself carries a tag,
# e.g. ABP-321-LTX.mp4 sitting next to ABP-321.srt.
#
# Restoration tools can append further marks AFTER the badge token, so the
# badge is not necessarily the last token: "JUR-110_restored_wm.mp4" and
# "SONE-521_restored.LTX_wm.mp4" both carry a "_wm" watermark mark (and the
# latter uses a dot as separator). Keep the same word list in every consumer
# of this rule. WM itself is NOT a badge - a bare "ABP-321_wm.mp4" stays plain.
#
# NOTE: Plex compiles plug-in modules with RestrictedPython, which rejects any
# module-level name starting with an underscore ("_BADGE_TOKEN" caused
# "SyntaxError: ... is an invalid variable name because it starts with '_'").
# Keep these helpers underscore-free, even though plain Python allows it.
BADGE_TOKEN_PATTERN = (r'(UNCENSORED|UC|C|CH|U|LTX|RESTORED|'
                       r'BASICVSR\+\+|BASICVSR)')
TOOL_TOKEN_PATTERN = (r'(?:WM|UNCENSORED|UC|C|CH|U|LTX|RESTORED|'
                      r'BASICVSR\+\+|BASICVSR)')
# Capture the LAST badge token in the chain, so the report keeps showing the
# most specific mark (e.g. RESTORED for "X_LTX__restored").
TRAILING_BADGE_TAG = re.compile(
    r'[-_.\s]+(?:' + TOOL_TOKEN_PATTERN + r'[-_.\s]+)*' +
    BADGE_TOKEN_PATTERN +
    r'(?:[-_.\s]+' + TOOL_TOKEN_PATTERN + r')*$',
    re.IGNORECASE)


def subtitle_name_candidates(video_name):
    """Basenames a subtitle may legitimately use for ``video_name``.

    ``ABP-321-LTX`` yields ``ABP-321-LTX`` and ``ABP-321``, so a subtitle named
    after the bare number is still accepted.
    """
    basename = as_unicode(
        os.path.splitext(os.path.basename(video_name))[0])
    candidates = [basename.upper()]
    current = basename
    while True:
        match = TRAILING_BADGE_TAG.search(current)
        if not match or match.start() == 0:
            break
        current = current[:match.start()]
        candidates.append(current.upper())
    return candidates


def has_bare_subtitle(video_name):
    """Check for a bare same-name subtitle file next to the video.

    A "bare" subtitle has no language tag at all, e.g. ``ABP-321.srt`` sitting
    next to ``ABP-321.mp4``. For JAV libraries such files are almost always
    Chinese subtitles, so they count as Chinese even though the filename does
    not carry a ``chs`` / ``zh`` marker.
    """
    if not probe(os.path.exists, video_name):
        return False
    candidates = subtitle_name_candidates(video_name)
    for filename in list_dir_names(os.path.dirname(video_name) or '.'):
        name = as_unicode(filename)
        if name.startswith('.') or name.startswith('~'):
            continue
        stem, ext = os.path.splitext(os.path.basename(name))
        if ext.lower()[1:] not in BARE_SUBTITLE_EXTENSIONS:
            continue
        if stem.upper() in candidates:
            return True
    return False


def get_badge_type(video_name, chinese_subtitle_on=False):
    name, ext = os.path.splitext(
        os.path.basename(video_name))
    if ext.lower() not in VIDEO_EXTENSIONS:
        return None

    name = as_unicode(name)
    # A dot is a separator too: "SONE-521_restored.LTX_wm" must still expose
    # the RESTORED token instead of the glued "RESTORED.LTX".
    values = [i for i in re.split(r'[-._\s]', name.upper()) if i]

    has_uc_tag = 'UC' in values
    # NOTE: do not use any()/all() here. Plex runs plug-ins with a reduced
    # builtins set and ``any`` is not available, which raised NameError and
    # killed the whole badge decision for every -U / -LTX / -C file (only -UC
    # survived, because the ``or`` above short-circuits before the call).
    has_u_tag = has_uc_tag
    if not has_u_tag:
        for tag in UNCENSORED_TAGS:
            if tag in values:
                has_u_tag = True
                break

    # Evidence from the file name first: it cannot fail, and "-U" / "-LTX"
    # alone already settles the uncensored part. The folder scans below are
    # just hints about external subtitles; on a NAS they can raise for
    # undecodable names, which used to discard a perfectly good "-LTX" match
    # and leave the movie with no badge and no tag at all.
    has_name_c_tag = (chinese_subtitle_on or
                      as_unicode(CHINESE_SUBTITLE) in name or
                      'C' in values or 'CH' in values)

    if has_uc_tag:
        return BADGE_TYPE_CHINESE_UNCENSORED

    if has_u_tag:
        # A subtitle next to the video upgrades "uncensored" to "uncensored +
        # Chinese", but a failed scan must keep the plain uncensored result.
        if (has_name_c_tag or
                probe(has_bare_subtitle, video_name) or
                probe(has_external_chinese_subtitle, video_name)):
            return BADGE_TYPE_CHINESE_UNCENSORED
        return BADGE_TYPE_UNCENSORED

    if (has_name_c_tag or
            probe(has_bare_subtitle, video_name) or
            probe(has_external_chinese_subtitle, video_name)):
        return BADGE_TYPE_CHINESE
    return None


def get_badge_type_from_files(video_names, chinese_subtitle_on=False):
    """First badge type detected across the given video files.

    The Chinese-subtitle hint is applied per file, not to the whole list: an
    item holding two versions (``DLDSS-534.mp4`` next to ``DLDSS-534-UC.mp4``)
    used to inherit the flag from whichever copy carried a subtitle, so the
    plain file was reported as "c" and the ``-UC`` marker of its sibling was
    ignored. The badge then claimed "中文字幕" for an uncensored release.
    """
    for video_name in video_names or ():
        hint = chinese_subtitle_on and probe(has_chinese_subtitle, video_name)
        badge_type = get_badge_type(video_name, hint)
        if badge_type:
            return badge_type
    return None


def get_badge_name(video_names, chinese_subtitle_on=False,
                   chinese='zimu.png', uncensored='u.png', both='uc.png'):
    return get_badge_name_from_type(
        get_badge_type_from_files(video_names, chinese_subtitle_on),
        chinese=chinese, uncensored=uncensored, both=both)


def get_badge_name_from_type(badge_type,
                             chinese='zimu.png', uncensored='u.png', both='uc.png'):
    if badge_type == BADGE_TYPE_CHINESE_UNCENSORED:
        return both
    if badge_type == BADGE_TYPE_UNCENSORED:
        return uncensored
    if badge_type == BADGE_TYPE_CHINESE:
        return chinese
    return None


def get_type_tags(badge_type, chinese=None, uncensored=None, both=None):
    """Plex genres (类型) to add for a badge type.

    ``chinese`` and ``uncensored`` are orthogonal, so a UC video gets both tags
    and filtering on 中文字幕 also returns UC titles. ``both`` is optional and
    appends an extra tag (e.g. 中文无码) only when configured.
    """
    tags = []
    if badge_type in (BADGE_TYPE_CHINESE, BADGE_TYPE_CHINESE_UNCENSORED):
        tags.append(chinese or CHINESE_SUBTITLE)
    if badge_type in (BADGE_TYPE_UNCENSORED, BADGE_TYPE_CHINESE_UNCENSORED):
        tags.append(uncensored or TYPE_TAG_UNCENSORED)
    if badge_type == BADGE_TYPE_CHINESE_UNCENSORED and both:
        tags.append(both)
    return tags


def extra_media_parts(obj):
    if not hasattr(obj, 'all_parts'):
        return ()
    return [part for part in obj.all_parts()
            if hasattr(part, 'file') and hasattr(part, 'duration')]


def extra_media_durations(obj):
    parts = extra_media_parts(obj)

    # single file version
    if len(parts) == 1:
        return {parts[0].file: int(parts[0].duration)}

    # multi-disk file match
    r = re.compile(r'-\s*(cd|disc|disk|dvd|pt|part)(\d+)$', re.IGNORECASE)

    durations = {}
    for part in parts:
        if int(part.duration) > 0:
            name, ext = os.path.splitext(part.file)

            if r.search(name):
                key = re.sub(r'\d+$', '', name) + ext
            else:
                key = name + ext

            durations.setdefault(key, 0)
            durations[key] = durations[key] + int(part.duration)

    return durations


# ---------------------------------------------------------------------------
# Translation quality gate
#
# A translation engine fails in two very different ways: the request fails
# outright (quota exhausted, timeout, EOF), or it answers with something that
# is not a usable translation at all - the Japanese original, or page
# furniture instead of text (seen in production: BaiduAI nmt answering a
# summary with "您的位置：知道爆料馆..."). translator.py treats the two cases
# differently, so the second kind has to be recognised here.
# ---------------------------------------------------------------------------

# Tolerated: a real name such as 朝妃りお keeps its kana in a Chinese
# translation, so a few kana characters cannot mean "not translated".
KANA_MINOR_RATIO = 0.02
KANA_UNTRANSLATED_RATIO = 0.15
TRANSLATION_MIN_RATIO = 0.2
TRANSLATION_MAX_RATIO = 3.0

KANA_RANGES = ((0x3040, 0x309F), (0x30A0, 0x30FF), (0xFF66, 0xFF9D))
HANGUL_RANGE = (0xAC00, 0xD7AF)
CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))

TRANSLATION_POLLUTION_MARKERS = (
    u'您的位置', u'知道爆料馆', u'点击进入', u'更多知识', u'百度百科',
    u'版权所有', u'返回首页', u'相关推荐',
)

CHINESE_TARGET_MARKERS = ('zh', 'cn', 'chi', 'hans', 'hant')


def in_charset(ch, ranges):
    o = ord(ch)
    for low, high in ranges:
        if low <= o <= high:
            return True
    return False


def charset_ratio(text, ranges):
    if not text:
        return 0.0
    hits = 0
    for ch in text:
        if in_charset(ch, ranges):
            hits = hits + 1
    return float(hits) / len(text)


def is_chinese_target(target):
    """True when the requested output language is Chinese.

    ``target`` may be a locale code like 'zh' / 'zh-Hans' or a Locale object;
    anything unrecognised is treated as Chinese, which is the plug-in default.
    """
    if not target:
        return True
    code = u'{0}'.format(target).strip().lower()
    if not code:
        return True
    for marker in CHINESE_TARGET_MARKERS:
        if marker in code:
            return True
    return False


def to_text(value):
    """Coerce a value to text so byte strings cannot trip the gate below."""
    if value is None:
        return u''
    if isinstance(value, type(u'')):
        return value
    try:
        return value.decode('utf-8')
    except AttributeError:
        return u'{0}'.format(value)
    except Exception:
        return u'{0}'.format(value)


def looks_translated(text, source=None, target=None):
    """Judge whether ``text`` is a usable translation of ``source``.

    Returns ``(ok, reason)``. ``ok`` is False when the text should not be
    written into Plex; ``reason`` is a short machine-readable explanation that
    ends up in the log, so a bad batch can be recognised later.
    """
    text = to_text(text)
    source = to_text(source) if source else None

    if not text:
        return False, 'empty'

    kana = charset_ratio(text, KANA_RANGES)
    if kana > KANA_UNTRANSLATED_RATIO:
        return False, 'untranslated (kana {0:.0f}%)'.format(kana * 100)

    if charset_ratio(text, (HANGUL_RANGE,)) > 0.2:
        return False, 'untranslated (hangul)'

    for marker in TRANSLATION_POLLUTION_MARKERS:
        if marker in text:
            return False, 'polluted ({0})'.format(marker)

    if source:
        if text.strip() == source.strip():
            return False, 'identical to source'
        length_ratio = float(len(text)) / max(len(source), 1)
        if length_ratio < TRANSLATION_MIN_RATIO:
            return False, 'too short ({0:.0%} of source)'.format(length_ratio)
        if length_ratio > TRANSLATION_MAX_RATIO:
            return False, 'too long ({0:.0f}x source)'.format(length_ratio)

    if is_chinese_target(target):
        if charset_ratio(text, CJK_RANGES) <= 0:
            return False, 'no Chinese characters'

    if kana > KANA_MINOR_RATIO:
        return True, 'kana-minor ({0:.0f}%)'.format(kana * 100)
    return True, 'ok'


def split_words(s, sep=','):
    """Split a comma separated list, keeping the original letter case.

    ``parse_list`` uppercases everything, which would turn engine names such as
    ``BaiduAI`` into ``BAIDUAI`` and break the lookup.
    """
    if not s:
        return []
    return [i.strip() for i in s.split(sep) if i.strip()]


def filter_prefixed(table, prefix):
    """Return the entries of ``table`` that belong to ``prefix``, unprefixed.

    Used for the shared fallback parameter table, which stores per-engine
    credentials as ``baidu.appid=...`` / ``deepl.auth_key=...``.
    """
    if not table or not prefix:
        return {}
    head = prefix.strip().lower() + '.'
    out = {}
    for key in table:
        if key.lower().startswith(head):
            out[key[len(head):]] = table[key]
    return out
