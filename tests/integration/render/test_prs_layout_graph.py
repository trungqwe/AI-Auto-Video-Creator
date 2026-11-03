"""PRS-LAYOUT-DOMAIN: compose_layout dựng đúng năm bố cục qua FFmpeg ghim thật (ảnh nhỏ tự tạo, không mạng, không CSDL).

Mỗi ô ảnh hiện đúng ảnh được giao ở đúng toạ độ của layout_geometry; băng màu nhấn mang màu của preset; ở nhánh render chỉ ô chính
chuyển động, mọi lớp khác đứng yên; khung đầu của nhánh render trùng khung tĩnh của nhánh QC (cùng một hàm dựng).

coveredIds: FR-PRS-001, FR-PRS-002, FR-PRS-006
"""
import struct
import subprocess
import zlib

import pytest

from render.adapters.real_ffmpeg_renderer import DEFAULT_FFMPEG_PATH
from render.domain import layout

W, H = 540, 960
ACCENT = '#00F0FF'
ACCENT_RGB = (0, 240, 255)
COLOURS = [(220, 30, 30), (30, 200, 60), (40, 60, 230), (230, 200, 20), (200, 40, 200)]


def write_png(path, width, height, pixel):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
    raw = b''.join(b'\x00' + b''.join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    path.write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def solid_images(tmp_path, count):
    paths = []
    for k in range(count):
        path = tmp_path / f'img{k}.png'
        width, height = (64, 36) if k % 2 == 0 else (36, 64)
        write_png(path, width, height, lambda x, y, c=COLOURS[k]: c)
        paths.append(path)
    return paths


def frames_of(paths, graph, count):
    argv = [DEFAULT_FFMPEG_PATH, '-hide_banner', '-nostdin', '-v', 'error']
    for path in paths:
        argv += ['-i', str(path)]
    argv += ['-filter_complex', graph + ',setsar=1,fps=30,format=rgb24[out]', '-map', '[out]', '-frames:v', str(count), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
    done = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, timeout=300, check=False)
    assert done.returncode == 0, done.stderr.decode('utf-8', 'replace')[-2000:]
    size = W * H * 3
    assert len(done.stdout) == size * count
    return [done.stdout[k * size:(k + 1) * size] for k in range(count)]


def pixel(frame, x, y):
    at = (y * W + x) * 3
    return tuple(frame[at:at + 3])


def near(found, wanted, tolerance=18):
    return all(abs(a - b) <= tolerance for a, b in zip(found, wanted))


def centre(box):
    scaled = layout._scaled(box, W, H)
    return scaled.x + scaled.w // 2, scaled.y + scaled.h // 2


def test_each_layout_draws_each_image_in_its_cell_and_the_accent_band(tmp_path):
    images = solid_images(tmp_path, 5)
    for key in layout.LAYOUT_KEYS:
        geometry = layout.layout_geometry(key)
        cells = geometry.cells
        labels = [f'{k}:v' for k in range(len(cells))]
        graph = layout.compose_layout(key, width=W, height=H, sources=labels, accent=ACCENT, prefix='q')
        frame = frames_of(images[:len(cells)], graph, 1)[0]
        for k, cell in enumerate(cells):
            inner = layout.Box(cell.box.x + cell.border, cell.box.y + cell.border, cell.box.w - 2 * cell.border, cell.box.h - 2 * cell.border)
            later = [layer.box for layer in geometry.layers[geometry.layers.index(cell) + 1:]]
            spots = [(inner.x + inner.w * fx, inner.y + inner.h * fy) for fx in (0.2, 0.5, 0.8, 0.97) for fy in (0.2, 0.5, 0.8)]
            free = [(x, y) for x, y in spots if not any(b.x <= x < b.right and b.y <= y < b.bottom for b in later)]
            assert free, (key, cell.name)
            x, y = free[0]
            found = pixel(frame, round(x * W / 1080), round(y * H / 1920))
            assert near(found, COLOURS[k]), (key, cell.name, found, COLOURS[k])
        for shape in (layer for layer in geometry.layers if isinstance(layer, layout.Shape) and layer.colour == 'accent' and layer.box.h >= 40 and layer.radius == 0):
            x, y = centre(shape.box)
            assert near(pixel(frame, x, y), ACCENT_RGB), (key, shape.name, pixel(frame, x, y))


def test_render_branch_moves_only_the_main_cell_and_starts_at_the_qc_frame(tmp_path):
    images = solid_images(tmp_path, 4)
    stripes = tmp_path / 'stripes.png'
    write_png(stripes, 120, 80, lambda x, y: (255, 255, 255) if (x // 6) % 2 else (0, 0, 0))
    paths = [stripes, *images[1:4]]
    labels = [f'{k}:v' for k in range(4)]
    still = frames_of(paths, layout.compose_layout('HERO_STRIP', width=W, height=H, sources=labels, accent=ACCENT, prefix='q'), 1)[0]
    moving = frames_of(paths, layout.compose_layout('HERO_STRIP', width=W, height=H, sources=labels, accent=ACCENT, prefix='s0', frames=40, fps=30), 40)
    main = layout._scaled(layout.Box(40, 510, 1000, 620), W, H)
    strip = layout._scaled(layout.Box(380, 1160, 320, 190), W, H)

    def region(frame, box):
        return [pixel(frame, x, y) for y in range(box.y + 4, box.bottom - 4, 7) for x in range(box.x + 4, box.right - 4, 7)]

    def diff(a, b):
        pa, pb = region(a[0], a[1]), region(b[0], b[1])
        return sum(abs(p - q) for u, v in zip(pa, pb) for p, q in zip(u, v)) / (3 * len(pa))

    assert diff((moving[0], main), (moving[-1], main)) > 20
    assert diff((moving[0], strip), (moving[-1], strip)) < 1
    assert diff((moving[0], main), (still, main)) < 3
    assert diff((moving[0], strip), (still, strip)) < 1


def test_frame_with_shared_chrome_equals_the_qc_frame(tmp_path):
    images = solid_images(tmp_path, 5)
    for key in layout.LAYOUT_KEYS:
        count = len(layout.layout_geometry(key).cells)
        labels = [f'{k}:v' for k in range(count)]
        qc = frames_of(images[:count], layout.compose_layout(key, width=W, height=H, sources=labels, accent=ACCENT, prefix='q'), 1)[0]
        chains, under, above = layout.compose_chrome(key, width=W, height=H, accent=ACCENT, prefix='c')
        shared = chains + ';' + layout.compose_layout(key, width=W, height=H, sources=labels, accent=ACCENT, prefix='s0', chrome=(under, above))
        assert frames_of(images[:count], shared, 1)[0] == qc, key
