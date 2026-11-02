"""ADAPT-A-FIX1 (OI-CP7-11-Q1): offline tests for article page images, header based image size and the 12 image cap."""
from __future__ import annotations

import json

import pytest

from controlplane.domain.common.contracts import ProblemDetail
from source_ingestion.adapters import real_media_fetch
from source_ingestion.adapters.article_images import MAX_PAGE_IMAGES, PageImage, decode_html, page_images
from source_ingestion.adapters.image_header import read_image_size
from source_ingestion.adapters.real_feed_source import ADAPTER_VERSION, RealFeedSource
from source_ingestion.adapters.real_media_fetch import RealMediaFetcher, StagedImage
from source_ingestion.adapters.secure_fetch import FetchPolicy, SecureFetcher, TransportResponse
from source_ingestion.ports.source_adapter import ExtractedCandidate, FetchedDocument

PUBLIC = '93.184.216.34'
BASE = 'https://news.example/a/1'


def hexb(text):
    return bytes.fromhex(text)


def png_header(width=640, height=480):
    ihdr = width.to_bytes(4, 'big') + height.to_bytes(4, 'big') + hexb('0802000000')
    return hexb('89504e470d0a1a0a') + (13).to_bytes(4, 'big') + b'IHDR' + ihdr + bytes(4)


def jpeg_header(width=640, height=480, marker=0xC0):
    app0 = hexb('ffe0') + (16).to_bytes(2, 'big') + b'JFIF' + bytes(1) + hexb('010100000100010000')
    sof = bytes([0xFF, marker]) + (17).to_bytes(2, 'big') + bytes([8]) + height.to_bytes(2, 'big') + width.to_bytes(2, 'big') + hexb('03012200021101031101')
    return hexb('ffd8') + app0 + sof + hexb('ffda') + bytes(20)


def jpeg_with_exif_thumbnail(width, height):
    payload = b'Exif' + bytes(2) + jpeg_header(160, 120)
    app1 = hexb('ffe1') + (len(payload) + 2).to_bytes(2, 'big') + payload
    base = jpeg_header(width, height)
    return base[:2] + app1 + base[2:]


def webp(chunk, body):
    payload = chunk + len(body).to_bytes(4, 'little') + body
    return b'RIFF' + (len(payload) + 4).to_bytes(4, 'little') + b'WEBP' + payload


def webp_vp8(width, height):
    return webp(b'VP8 ', hexb('300100') + hexb('9d012a') + width.to_bytes(2, 'little') + height.to_bytes(2, 'little') + bytes(8))


def webp_vp8l(width, height):
    bits = (width - 1) | ((height - 1) << 14)
    return webp(b'VP8L', hexb('2f') + bits.to_bytes(4, 'little') + bytes(8))


def webp_vp8x(width, height):
    return webp(b'VP8X', bytes(4) + (width - 1).to_bytes(3, 'little') + (height - 1).to_bytes(3, 'little') + bytes(8))


VALID = [
    (png_header(640, 480), (640, 480)),
    (png_header(360, 360), (360, 360)),
    (jpeg_header(800, 600), (800, 600)),
    (jpeg_header(1200, 630, 0xC1), (1200, 630)),
    (jpeg_header(1024, 768, 0xC2), (1024, 768)),
    (jpeg_with_exif_thumbnail(1600, 900), (1600, 900)),
    (webp_vp8(500, 400), (500, 400)),
    (webp_vp8l(700, 360), (700, 360)),
    (webp_vp8x(1920, 1080), (1920, 1080)),
]
BROKEN = [
    None, b'', hexb('ffd8'), hexb('ffd8ffd9'), jpeg_header()[:10], jpeg_header()[:25],
    hexb('ffd8ffda') + bytes(20), jpeg_header(0, 480), hexb('ffd8ffe00001') + bytes(30), hexb('ffd8') + bytes(10),
    hexb('89504e470d0a1a0a'), png_header()[:20], png_header(0, 480), png_header(640, 0),
    png_header().replace(b'IHDR', b'IDAT'), webp_vp8(500, 400)[:28], webp_vp8(0, 400),
    webp_vp8(500, 400).replace(hexb('9d012a'), bytes(3)),
    webp_vp8l(700, 360)[:20] + bytes(1) + webp_vp8l(700, 360)[21:],
    webp(b'ABCD', bytes(20)), b'GIF89a' + bytes(30),
]


@pytest.mark.parametrize('data, size', VALID)
def test_read_image_size_reads_jpeg_png_and_webp_headers(data, size):
    assert read_image_size(data) == size


@pytest.mark.parametrize('data', BROKEN)
def test_read_image_size_gives_none_for_damaged_or_zero_headers(data):
    assert read_image_size(data) is None


def test_read_image_size_never_raises_on_any_prefix():
    for data, _ in VALID:
        for cut in range(len(data) + 1):
            result = read_image_size(data[:cut])
            assert result is None or (len(result) == 2 and min(result) > 0)


IMAGE_POLICY = FetchPolicy(
    revision='fix1', max_redirects=2, max_body_bytes=1 << 20,
    allowed_media_types=frozenset({'image/jpeg', 'image/png', 'image/webp'}), timeout_seconds=10.0,
)


class Site:
    """Fixed (content type, body) pairs by locator; records every requested locator."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def send(self, request):
        self.requests.append(request.locator)
        content_type, body = self.routes[request.locator]
        return TransportResponse(200, (('Content-Type', content_type),), [body])


def make_media(routes, tmp_path, **kwargs):
    site = Site(routes)
    fetcher = SecureFetcher(site, lambda host: [PUBLIC])
    media = RealMediaFetcher(fetcher, image_policy=IMAGE_POLICY, staging_root=tmp_path / 'staging', **kwargs)
    return media, site


def test_fetch_image_keeps_only_readable_headers_with_a_short_side_of_360(tmp_path):
    base = 'https://img.example/'
    served = {
        'square.png': ('image/png', png_header(360, 360) + bytes(64)),
        'mislabeled.png': ('image/png', jpeg_header(800, 600) + bytes(32)),
        'narrow.png': ('image/png', png_header(359, 2000)),
        'flat.jpg': ('image/jpeg', jpeg_header(2000, 359)),
        'tiny.jpg': ('image/jpeg', png_header(100, 100)),
        'broken.jpg': ('image/jpeg', hexb('ffd8') + bytes(40)),
        'text.png': ('image/png', b'not an image header at all'),
    }
    media, _ = make_media({base + name: value for name, value in served.items()}, tmp_path)
    results = {name: media.fetch_image(base + name, role='inline', source_ref='s', article_ref='a') for name in served}
    kept = [results['square.png'], results['mislabeled.png']]
    assert all(isinstance(item, StagedImage) for item in kept)
    for name in ('narrow.png', 'flat.jpg', 'tiny.jpg'):
        problem = results[name]
        assert isinstance(problem, ProblemDetail) and problem.code == 'IMAGE_TOO_SMALL'
        assert problem.category == 'policy' and problem.retryable is False and problem.min_short_side == 360
    assert (results['narrow.png'].width, results['narrow.png'].height) == (359, 2000)
    assert (results['flat.jpg'].width, results['flat.jpg'].height) == (2000, 359)
    assert results['narrow.png'].detail == results['flat.jpg'].detail
    for name in ('broken.jpg', 'text.png'):
        problem = results[name]
        assert isinstance(problem, ProblemDetail) and problem.code == 'IMAGE_HEADER_UNREADABLE' and problem.retryable is False
    assert {path.name for path in (tmp_path / 'staging').iterdir()} == {item.staged_path.name for item in kept}
    assert real_media_fetch.MIN_SHORT_SIDE == 360


def test_fetch_article_media_default_cap_is_12_attempts(tmp_path):
    routes = {f'https://img.example/p{n}.png': ('image/png', png_header(640, 480)) for n in range(15)}
    media, site = make_media(routes, tmp_path)
    items = [{'locator': locator, 'role': 'inline', 'media_kind': 'image'} for locator in routes]
    batch = media.fetch_article_media(items, source_ref='s', article_ref='a')
    assert len(site.requests) == 12
    assert len(batch.staged) == 12 and batch.problems == ()
    assert real_media_fetch.MAX_IMAGES_PER_ARTICLE == 12


def locators(images):
    return [image.locator for image in images]


def triples(images):
    return [(image.locator, image.role, image.element) for image in images]


GU = 'https://i.guim.co.uk/img/media/aaaa1111bbbb2222/0_0_3000_2000/master/3000.jpg'
GU2 = 'https://i.guim.co.uk/img/media/cccc3333dddd4444/0_0_2400_1600/master/2400.jpg'
GU3 = 'https://i.guim.co.uk/img/media/eeee5555ffff6666/0_0_500_300/master/500.jpg'
OVERLAY = 'overlay-align=bottom%2Cleft&overlay-width=100p&overlay-base64=L2ltZy9zdGF0aWMvb3ZlcmxheXMvdGctZGVmYXVsdC5wbmc&enable=upscale'
SHARE = GU + '?width=1200&height=630&quality=85&auto=format&fit=crop&' + OVERLAY
GUARDIAN_LD = json.dumps({'@type': 'NewsArticle', 'image': [SHARE + '&s=ld']})
GUARDIAN = ''.join([
    '<html><head>',
    '<meta property="og:image" content="' + SHARE.replace('&', '&amp;') + '&amp;s=og">',
    '<meta name="twitter:image" content="' + SHARE.replace('&', '&amp;') + '&amp;s=tw">',
    '<script type="application/ld+json">' + GUARDIAN_LD + '</script>',
    '</head><body><header><img src="https://static.guim.co.uk/header-fixture.jpg" alt=""></header>',
    '<main><article><h1>Headline</h1>',
    '<figure><picture><source srcSet="' + GU + '?width=620&amp;dpr=1&amp;s=none" media="(min-width: 980px)">',
    '<img src="' + GU + '?width=300&amp;dpr=1&amp;s=none" alt="" width="300" height="200"></picture></figure>',
    '<p>Text</p><figure><img src="' + GU2 + '?width=620&amp;dpr=1&amp;s=none" alt="" width="620" height="413"></figure>',
    '<noscript><img src="https://sb.scorecardresearch.com/p?c1=2&amp;c2=6035250&amp;cj=1" alt=""></noscript>',
    '</article><aside><img src="' + GU3 + '?width=300&amp;dpr=1&amp;s=none" alt=""></aside></main>',
    '<footer><img src="https://static.guim.co.uk/logo.png" alt=""></footer></body></html>',
])


def test_guardian_keeps_only_the_clean_body_photos():
    images = page_images(GUARDIAN, 'https://www.theguardian.com/world/2026/nov/01/story')
    assert triples(images) == [
        (GU + '?width=620&dpr=1&s=none', 'inline', 'picture'),
        (GU2 + '?width=620&dpr=1&s=none', 'inline', 'img'),
    ]
    assert images[0] == PageImage(GU + '?width=620&dpr=1&s=none', 'inline', 'picture')
    assert not any('overlay' in image.locator or 'scorecardresearch' in image.locator for image in images)


def test_guardian_overlay_photo_stays_when_the_body_has_no_clean_variant():
    html = '<html><head><meta property="og:image" content="' + GU + '?width=1200&amp;height=630&amp;overlay-base64=QUJD&amp;s=og"></head><body><p>No images</p></body></html>'
    assert triples(page_images(html, BASE)) == [(GU + '?width=1200&height=630&overlay-base64=QUJD&s=og', 'hero', 'meta:og:image')]


def test_guardian_decode_html_uses_the_header_then_the_meta_charset():
    text = '<html><head><title>Café</title></head><body></body></html>'
    assert decode_html(text.encode('utf-8'), (('content-type', 'text/html; charset=utf-8'),)) == text
    assert decode_html(text.encode('latin-1'), (('content-type', 'text/html; charset=ISO-8859-1'),)) == text
    meta = '<html><head><meta charset="windows-1252"></head><body>Café</body></html>'
    assert decode_html(meta.encode('cp1252'), ()) == meta
    assert decode_html(text.encode('utf-8'), (('content-type', 'text/html; charset=no-such-charset'),)) == text


def bbc_uuid(n):
    return f'00000000-0000-4000-8000-{n:012d}'


def bbc_picture(n):
    path = f'cpsprodpb/ab12/live/{bbc_uuid(n)}.jpg'
    return (
        '<picture><source srcset="https://ichef.bbci.co.uk/ace/standard/240/' + path + '.webp 240w, '
        'https://ichef.bbci.co.uk/ace/standard/976/' + path + '.webp 976w" type="image/webp">'
        '<img alt="" src="https://ichef.bbci.co.uk/ace/standard/976/' + path + '" width="976" height="549"></picture>'
    )


def bbc_webp(n):
    return f'https://ichef.bbci.co.uk/ace/standard/976/cpsprodpb/ab12/live/{bbc_uuid(n)}.jpg.webp'


def bbc_og(n):
    return f'https://ichef.bbci.co.uk/ace/branded_news/1200/cpsprodpb/ab12/live/{bbc_uuid(n)}.jpg'


def bbc_page(og, article, outside):
    return ('<html><head><meta property="og:image" content="' + og + '"></head><body><header>' + bbc_picture(99)
            + '</header><main><article><h1>News</h1>' + article + '</article><section>' + outside + '</section></main></body></html>')


def test_bbc_branded_og_loses_to_the_body_photo_and_only_article_photos_stay():
    page = bbc_page(bbc_og(1), bbc_picture(1) + bbc_picture(2), ''.join(bbc_picture(n) for n in range(10, 20)))
    images = page_images(page, 'https://www.bbc.com/news/world-1')
    assert triples(images) == [(bbc_webp(1), 'inline', 'picture'), (bbc_webp(2), 'inline', 'picture')]
    assert not any('branded_news' in image.locator for image in images)


def test_bbc_og_photo_that_is_not_in_the_body_stays_as_hero():
    page = bbc_page(bbc_og(7), bbc_picture(1), '')
    assert triples(page_images(page, BASE)) == [(bbc_og(7), 'hero', 'meta:og:image'), (bbc_webp(1), 'inline', 'picture')]


def test_bbc_page_without_article_main_or_article_body_keeps_every_image_in_document_order():
    html = '<html><body><header>' + bbc_picture(1) + '</header><div>' + bbc_picture(2) + '</div><section>' + bbc_picture(3) + '</section></body></html>'
    assert locators(page_images(html, BASE)) == [bbc_webp(1), bbc_webp(2), bbc_webp(3)]


def img(name):
    return '<img src="https://img.example/r/' + name + '.jpg" alt="">'


REGIONS = [
    ('<main>' + img('m') + '</main><div itemprop="articleBody">' + img('b') + '</div><article>' + img('a') + '</article>' + img('p'), ['a']),
    ('<div>' + img('p') + '</div><main>' + img('m') + '<div itemprop="articleBody">' + img('b') + '</div></main>', ['b']),
    ('<nav>' + img('n') + '</nav><main>' + img('m') + '</main>' + img('p'), ['m']),
    ('<article><article>' + img('x') + '</article>' + img('y') + '</article>' + img('z'), ['x', 'y']),
    ('<p>' + img('before') + '</p><article>' + img('x') + '<p>text' + img('y'), ['x', 'y']),
    ('<article><p>Only text</p></article><article>' + img('z') + '</article>', []),
    ('<div itemprop="articleBody"><div>' + img('x') + '</div>' + img('y') + '</div>' + img('z'), ['x', 'y']),
    (img('a') + '<div>' + img('b') + '</div>', ['a', 'b']),
]


@pytest.mark.parametrize('body, expected', REGIONS)
def test_bbc_main_region_priority_article_then_article_body_then_main_then_page(body, expected):
    html = '<html><body>' + body + '</body></html>'
    assert locators(page_images(html, BASE)) == ['https://img.example/r/' + name + '.jpg' for name in expected]


def test_page_images_drop_unwanted_files_and_declared_or_query_small_images():
    keep = [
        'https://img.example/photos/photo-one.jpg',
        'https://img.example/photos/photo-two.png?width=800',
        'https://img.example/photos/iconic-skyline.jpg',
    ]
    drop = [
        'https://img.example/a/logo.svg', 'https://img.example/a/anim.gif', 'https://img.example/a/modern.avif',
        'https://img.example/a/site-logo.png', 'https://img.example/Brand/LOGO.PNG', 'https://img.example/ui/icons/share.png',
        'https://img.example/t/1x1.png', 'https://img.example/a/sized.jpg?w=150',
        'https://img.example/a/resized.jpg?resize=100,100', 'data:image/png;base64,AAAA', 'ftp://img.example/a/old.jpg',
    ]
    tags = ''.join('<img src="' + url + '" alt="">' for url in [keep[0]] + drop + keep[1:])
    html = '<html><body>' + tags + '<img src="https://img.example/a/tiny.jpg" width="100" height="80"></body></html>'
    assert locators(page_images(html, BASE)) == keep


def test_page_images_resolve_urls_against_base_href():
    html = '<html><head><base href="https://cdn2.example/root/"></head><body><img src="pic.jpg" alt=""></body></html>'
    assert locators(page_images(html, BASE)) == ['https://cdn2.example/root/pic.jpg']


X = 'https://img.example/s/'
SRC_CASES = [
    ('<img srcset="' + X + 'a-300.jpg 300w, ' + X + 'a-1200.jpg 1200w, ' + X + 'a-600.jpg 600w" src="' + X + 'a-small.jpg">', X + 'a-1200.jpg'),
    ('<img srcset="' + X + 'b-1x.jpg 1x, ' + X + 'b-2x.jpg 2x">', X + 'b-2x.jpg'),
    ('<img srcset="' + X + 'c-first.jpg, ' + X + 'c-second.jpg">', X + 'c-first.jpg'),
    ('<img data-srcset="' + X + 'd-400.jpg 400w, ' + X + 'd-900.jpg 900w" src="data:image/gif;base64,R0lGOD">', X + 'd-900.jpg'),
    ('<img data-src="' + X + 'e-lazy.jpg" src="' + X + 'e-src.jpg">', X + 'e-lazy.jpg'),
    ('<img data-original="' + X + 'f-orig.jpg">', X + 'f-orig.jpg'),
    ('<img data-lazy-src="' + X + 'g-lazy.jpg">', X + 'g-lazy.jpg'),
    ('<picture><source type="image/avif" srcset="' + X + 'h-9000.avif 9000w"><source type="image/webp" srcset="' + X + 'h-800.webp 800w">'
     '<source srcset="' + X + 'h-700.jpg 700w"><img src="' + X + 'h-640.jpg"></picture>', X + 'h-800.webp'),
    ('<img src="/media/rel.jpg">', 'https://news.example/media/rel.jpg'),
    ('<img src="//cdn.example/p/proto.jpg">', 'https://cdn.example/p/proto.jpg'),
]


@pytest.mark.parametrize('body, expected', SRC_CASES)
def test_page_images_choose_one_url_per_img_or_picture(body, expected):
    html = '<html><body>' + body + '</body></html>'
    assert locators(page_images(html, BASE)) == [expected]


LD_GRAPH = {'@context': 'https://schema.org', '@graph': [
    {'@type': 'Organization', 'image': 'https://img.example/ld/org-banner.jpg'},
    {'@type': 'Person', 'image': 'https://img.example/ld/person-face.jpg'},
    {'@type': 'NewsArticle', 'image': [
        'https://img.example/ld/story-1.jpg',
        {'@type': 'ImageObject', 'url': 'https://img.example/ld/story-2.jpg'},
        {'contentUrl': 'https://img.example/ld/story-3.jpg'},
    ]},
    {'@type': 'WebPage', 'image': 'https://img.example/ld/page-4.jpg'},
]}


def test_page_images_read_json_ld_graph_lists_objects_and_skip_person_and_organization():
    single = json.dumps({'@type': 'NewsArticle', 'image': 'https://img.example/ld/single.jpg'})
    html = ('<html><head><script type="application/ld+json">' + json.dumps(LD_GRAPH) + '</script>'
            '<script type="application/ld+json">{not json</script>'
            '<script type="application/ld+json">' + single + '</script></head><body></body></html>')
    names = ['story-1', 'story-2', 'story-3', 'page-4', 'single']
    assert triples(page_images(html, BASE)) == [(f'https://img.example/ld/{name}.jpg', 'hero', 'json-ld') for name in names]


def test_page_images_meta_order_is_og_then_twitter_with_variants():
    html = ('<html><head><meta name="twitter:image" content="https://img.example/m/tw.jpg">'
            '<meta property="og:image:secure_url" content="https://img.example/m/og-secure.jpg">'
            '<meta property="og:image" content="https://img.example/m/og.jpg">'
            '<meta name="twitter:image:src" content="https://img.example/m/tw-src.jpg"></head><body></body></html>')
    assert triples(page_images(html, BASE)) == [
        ('https://img.example/m/og-secure.jpg', 'hero', 'meta:og:image:secure_url'),
        ('https://img.example/m/og.jpg', 'hero', 'meta:og:image'),
        ('https://img.example/m/tw.jpg', 'hero', 'meta:twitter:image'),
        ('https://img.example/m/tw-src.jpg', 'hero', 'meta:twitter:image:src'),
    ]


def test_page_images_same_locator_keeps_the_role_of_the_first_place_and_one_entry():
    url = 'https://img.example/p/same.jpg'
    html = '<html><head><meta property="og:image" content="' + url + '"></head><body><article><img src="' + url + '" alt=""></article></body></html>'
    assert triples(page_images(html, BASE)) == [(url, 'hero', 'meta:og:image')]


def test_page_images_next_image_urls_with_different_url_parameter_are_two_photos():
    first = 'https://news.example/_next/image?url=%2Fuploads%2Fa.jpg&w=1080&q=75'
    second = 'https://news.example/_next/image?url=%2Fuploads%2Fb.jpg&w=1080&q=75'
    html = '<html><body><img src="' + first + '"><img src="' + second + '"></body></html>'
    assert locators(page_images(html, BASE)) == [first, second]


def test_page_images_hash_named_files_of_one_host_are_one_photo():
    name = '0123456789abcdef0123456789abcdef'
    html = ('<html><body><img src="https://cdn.example/a/' + name + '.jpg"><img src="https://cdn.example/b/' + name + '.png">'
            '<img src="https://other.example/c/' + name + '.jpg"></body></html>')
    assert locators(page_images(html, BASE)) == ['https://cdn.example/a/' + name + '.jpg', 'https://other.example/c/' + name + '.jpg']


def test_page_images_clean_variant_beats_watermark_variant_even_when_later():
    photo = 'https://img.example/w/photo.jpg'
    html = '<html><body><img src="' + photo + '?watermark=1"><img src="' + photo + '?v=2"></body></html>'
    assert locators(page_images(html, BASE)) == [photo + '?v=2']


def test_page_images_are_capped_at_12_in_document_order():
    tags = ''.join(f'<img src="https://img.example/cap/p{n}.jpg" alt="">' for n in range(20))
    html = '<html><head><meta property="og:image" content="https://img.example/cap/p0.jpg"></head><body><article>' + tags + '</article></body></html>'
    images = page_images(html, BASE)
    assert MAX_PAGE_IMAGES == 12 and len(images) == 12
    assert locators(images) == [f'https://img.example/cap/p{n}.jpg' for n in range(12)]
    assert images[0].role == 'hero'


def test_page_images_and_decode_html_never_raise():
    for html in ('', '<<<<>>> <img src', '<img src="http://[bad">', '<script type="application/ld+json">[[[[[[[[[[[[</script>', None, 5):
        assert page_images(html, BASE) == ()
    assert page_images('<img src="/x.jpg">', '') == ()
    assert decode_html(None, ()) == ''


HTML_POLICY = FetchPolicy(revision='fix1', max_redirects=2, max_body_bytes=1 << 20, allowed_media_types=frozenset({'text/html'}), timeout_seconds=10.0)
FEED_POLICY = FetchPolicy(revision='fix1', max_redirects=2, max_body_bytes=1 << 20, allowed_media_types=frozenset({'application/rss+xml'}), timeout_seconds=10.0)
FEED_URL = 'https://news.example/feed.xml'
ARTICLE_URL = 'https://news.example/a/1'
SHARED = 'https://img.example/photos/shared-photo.jpg'
OG_CARD = 'https://img.example/photos/og-card.jpg'
RSS = (
    '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>T</title><link>https://news.example/</link>'
    '<description>d</description><item><title>One</title><link>' + ARTICLE_URL + '</link>'
    '<enclosure url="' + SHARED + '" type="image/jpeg" length="1000"/></item></channel></rss>'
).encode('utf-8')
PARAGRAPH = '<p>' + 'The harbour workers reached a comprehensive agreement after long negotiations at the terminal. ' * 4 + '</p>'
ARTICLE_PAGE = (
    '<html><head><title>Port strike ends</title><meta property="og:image" content="' + OG_CARD + '"></head><body><article><h1>Port strike ends</h1>'
    + PARAGRAPH * 3 + '<img src="' + SHARED + '" alt="" width="800" height="450"></article></body></html>'
).encode('utf-8')


def test_extract_candidate_takes_page_images_and_dedupes_by_locator_only(tmp_path):
    site = Site({FEED_URL: ('application/rss+xml; charset=utf-8', RSS), ARTICLE_URL: ('text/html; charset=utf-8', ARTICLE_PAGE)})
    source = RealFeedSource(SecureFetcher(site, lambda host: [PUBLIC]), source_kind='rss_feed', feed_policy=FEED_POLICY, article_policy=HTML_POLICY)
    assert source.list_candidates(FEED_URL, None).locators == (ARTICLE_URL,)
    document = source.fetch_document(ARTICLE_URL)
    assert isinstance(document, FetchedDocument)
    candidate = source.extract_candidate(document)
    assert isinstance(candidate, ExtractedCandidate)
    media = candidate.technical_fields['media']
    assert [(m['role'], m['locator'], m['context']['element'], m['context']['position']) for m in media] == [
        ('enclosure', SHARED, 'enclosure', 0),
        ('hero', OG_CARD, 'meta:og:image', 1),
    ]
    assert ADAPTER_VERSION == '1.0.0'
