# B?o c?o b?ng ch?ng F-10-FIX1

## Nh?m l?i R9

G?i F-10-FIX1 gi?i quy?t to?n di?n nh?m l?i R9 trong l?nh render c?a ph?n h? Render:
- Tr??c khi s?a, `build_render_command` ??a m?i visual asset v?o FFmpeg ch? b?ng `-i <t?p>` r?i `concat=n=N`, kh?ng c? c? `-loop 1` hay `-t <th?i l??ng>`, d?n t?i ?nh t?nh ch? xu?t hi?n 1 khung h?nh (kho?ng 0,033 gi?y), l?m bi?n m?t khung h?nh cho ph? ?? v? disclosure.
- B? l?c `scale` ban ??u ??t sau `concat`, khi?n FFmpeg b? l?i khi c?c ?nh ??u v?o c? k?ch th??c kh?c nhau (l?i "Input link ... do not match" v?i m? tho?t kh?c 0).
- ?? d?i ??u ra kh?ng kh?p v?i th?i l??ng voice track do thi?u ??ng b? gi?a timeline v? ?? d?i ?m thanh th?c t?.

Gi?i ph?p ?? tri?n khai:
- T?nh th?i l??ng t?ng segment: `duration_ms = timeline.segments[i].end_ms - start_ms`. Ki?m tra ch?t ch? ?i?u ki?n bi?n (`INPUT_NOT_READY` khi thi?u ho?c kh?ng ph?i s? nguy?n, `INVALID_INPUT` khi `end_ms <= start_ms`).
- X?c ??nh `media_type` t? `record.input_artifacts` theo `ref`. V?i ?nh t?nh (`image/*`), ??a v?o FFmpeg b?ng `-loop 1 -framerate <fps> -t <gi?y> -i <t?p>`. V?i media kh?c, ??a v?o b?ng `-t <gi?y> -i <t?p>`.
- Chu?n ho? t?ng ??u v?o ??c l?p tr??c `concat` b?ng chu?i filter: `[{index}:v:0]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps},format={pixel_format}[v{index}]`.
- Sau `concat`, b? sung `tpad=stop_mode=clone:stop=-1` tr??c khi ??a qua `ass=filename=...`, ??ng th?i th?m c? `-shortest` v?o tham s? ??u ra ?? video lu?n d?i ??ng b?ng voice track.
- `redacted_argv` v? `spec_fingerprint` c?p nh?t ??ng b? theo c?u tr?c l?nh m?i. H?m `build_thumbnail_command` v? adapter `real_ffmpeg_renderer.py` ???c gi? nguy?n v?n kh?ng ??i.

## C?c t?p ?? s?a

- `src/render/domain/render_command.py`: B? sung `IMAGE_MEDIA_PREFIX`, `_duration_ms`, `_seconds`, `_is_still_image`, `_normalise`, c?p nh?t `_filter_graph`, `_make_spec` v? `build_render_command`.
- `tests/unit/render/test_f10_render_command_spec.py`: C?p nh?t c?u tr?c test graph m?i, b? sung c?c test ki?m tra `-loop`, `-t`, `-shortest`, chu?n ho? tr??c concat, ki?m tra t? ch?i ??u v?o kh?ng h?p l? v? 2 test ch?y FFmpeg ?? ghim th?t v?i ?nh k?ch th??c h?n h?p.
- `docs/delivery-evidence/f-10-fix1/report.md`: B?o c?o b?ng ch?ng th?c thi g?i F-10-FIX1.

L?u ?: `build_thumbnail_command` v? `src/render/adapters/real_ffmpeg_renderer.py` gi? nguy?n, kh?ng ??i.

## RED

- L?nh ki?m tra: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
- M? tho?t: `1`
- D?ng t?m t?t nguy?n v?n c?a pytest:
```text
17 failed, 153 passed in 0.84s
```

## GREEN

- L?nh ki?m tra: `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider`
- M? tho?t: `0`
- D?ng t?m t?t nguy?n v?n c?a pytest:
```text
170 passed in 1.85s
```

## L?nh ki?m

| B??c | L?nh ki?m tra | M? tho?t | K?t qu? |
| --- | --- | --- | --- |
| B??c 13 | `python -m pytest tests/unit/render/test_f10_render_command_spec.py -q -p no:cacheprovider` | 0 | 170 passed in 1.85s |
| B??c 14 | `python -c "import pathlib; s = pathlib.Path('src/render/domain/render_command.py').read_text(encoding='utf-8'); assert 'tpad=stop_mode=clone:stop=-1' in s and '-shortest' in s and '-loop' in s and 'setsar=1' in s and 'force_original_aspect_ratio=increase' in s and "f'scale={width}:{height}'," not in s"` | 0 | ??t (probe R9 th?nh c?ng, kh?ng AssertionError) |
| B??c 15 | `python -m pytest tests/integration/adapt/f/test_adapt_f_render.py -q -p no:cacheprovider` | 1 | 1 failed, 53 passed in 3.91s |
| B??c 17 | `python -c "import pathlib; t = pathlib.Path('docs/delivery-evidence/f-10-fix1/report.md').read_text(encoding='utf-8'); assert 'F-10-FIX1' in t and 'R9' in t, 'report'"` | 0 | ??t (b?o c?o c? F-10-FIX1 v? R9) |
| B??c 18 | `git diff --check` | 0 | ??t (kh?ng c? l?i ??nh d?ng hay kho?ng tr?ng th?a) |

## ?nh h??ng ngo?i owned paths

- K?t qu? b??c 15 khi ch?y ki?m th? ngo?i owned paths (`tests/integration/adapt/f/test_adapt_f_render.py`):
  - M? tho?t: `1`
  - D?ng t?m t?t nguy?n v?n:
  ```text
  1 failed, 53 passed in 3.91s
  ```
  - Test b? fail: `test_command_is_an_argument_list_with_production_parameters` t?i d?ng 182.
  - Nguy?n nh?n: Test assert chu?i con `'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30'` trong filter graph. Tuy nhi?n, theo y?u c?u nghi?m thu b?t bu?c c?a R9, th? t? filter chu?n ho? ph?i c? `setsar=1` chen gi?a crop v? fps: `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p`.
  - T?p `tests/integration/adapt/f/test_adapt_f_render.py` n?m ngo?i owned paths c?a g?i F-10-FIX1 n?n Worker ch? ghi nh?n b?ng ch?ng v? kh?ng t? ? ch?nh s?a; c?n Control ho?c g?i ch? c?p nh?t t??ng ?ng.

## Quy?t ??nh

- Ref kh?ng c? trong danh s?ch `input_artifacts` ???c m?c ??nh coi l? lo?i media kh?c (kh?ng ph?i ?nh t?nh) v? ??a v?o FFmpeg b?ng c? `-t <gi?y> -i`.
- K? t? d?u ch?m ph?y `;` ch? ???c ph?p duy nh?t trong ph?n t? ??ng ngay sau c? `-filter_complex` ?? ph?n t?ch c?c chu?i filter graph; t?t c? c?c ph?n t? argv kh?c (profile, tools, file paths) v?n b? c?m nghi?m ng?t ?? ??m b?o an to?n injection.
- ???ng d?n file ASS subtitles v? karaoke gi? nguy?n c? ch? escape c?a adapter.

## Gi?i h?n

- Nh?m l?i R10 (ph?n gi?i hook placement, thumbnail timing ngo?i hook range) ch?a thu?c ph?m vi c?a g?i F-10-FIX1.
- Tu?n th? quy chu?n qu?n tr? t?c v?: ch? ch?y targeted tests theo work order, kh?ng t? ? ch?y full regression suite ?? ti?t ki?m t?i nguy?n v? th?i gian.
