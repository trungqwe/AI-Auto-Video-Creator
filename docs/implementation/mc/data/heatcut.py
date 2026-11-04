"""heatcut v2: chọn đoạn nóng N giây chỉ bằng ffmpeg/ffprobe (stdlib + numpy).
CLI: heatcut.py <video> [--window 4] [--w-motion 0.4] [--out json] [--sheets dir]
Chuỗi có độ phân giải BIN=0,5 s; cửa sổ trượt bước 0,5 s."""
import argparse, json, os, re, subprocess, time
import numpy as np
FF = "C:/ffmpeg/bin/ffmpeg.exe"; FP = "C:/ffmpeg/bin/ffprobe.exe"
BIN = 0.5; CUT_T = 0.3; CROSS_PENALTY = 0.9
NO_ACTION_MOTION = 0.004   # motion nội cảnh lớn nhất (điểm scene <= 0,3) dưới mức này = ảnh tĩnh
NO_ACTION_AUDIO_LU = 3.0   # và biên độ LUFS dưới mức này = giọng đều / im

def run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")

def probe(v):
    j = json.loads(run([FP, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", v]).stdout)
    return float(j["format"]["duration"]), any(s.get("codec_type") == "audio" for s in j["streams"])

def audio_series(v, nb):
    r = run([FF, "-nostats", "-threads", "2", "-i", v, "-vn", "-af", "ebur128", "-f", "null", "-"])
    s = np.zeros(nb); c = np.zeros(nb)
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET:\S+\s+LUFS\s+M:\s*(-?[\d.]+|-inf)", r.stderr):
        b = int(max(float(m.group(1)) - 0.3, 0) / BIN)  # M cửa sổ 400 ms báo ở cuối + độ trễ nhả: lùi 0,3 s
        if b >= nb: continue
        x = m.group(2); s[b] += -70.0 if x == "-inf" else max(float(x), -70.0); c[b] += 1
    if c.sum() == 0: return None
    c[c == 0] = 1
    return s / c

def motion_series(v, nb):
    r = run([FF, "-nostats", "-threads", "2", "-i", v, "-an", "-vf",
             "scale=160:-2,select='gte(scene,0)',metadata=print:file=-", "-f", "null", "-"])
    pts = None; sc = np.zeros(nb); cnt = np.zeros(nb); cuts = []
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m: pts = float(m.group(1)); continue
        m = re.search(r"lavfi.scene_score=([\d.]+)", line)
        if m and pts is not None:
            s = float(m.group(1)); b = min(int(pts / BIN), nb - 1)
            if s > CUT_T: cuts.append(round(pts, 2))   # khung chuyển cảnh: không tính vào motion
            else: sc[b] += s; cnt[b] += 1
    cnt[cnt == 0] = 1
    return sc / cnt, cuts

def mm(x):
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)

def pick(heat, cuts, dur, W):
    if dur < 10: return 0.0, dur, float(heat.sum()), "clip < 10 s: dùng nguyên"
    k = int(round(W / BIN)); nb = len(heat)
    if nb < k: return 0.0, dur, float(heat.sum()), "clip ngắn hơn cửa sổ"
    best = None
    for i in range(0, nb - k + 1):
        a, b = i * BIN, i * BIN + W
        cross = any(a + 0.05 < c < b - 0.05 for c in cuts)
        tot = heat[i:i + k].sum() * (CROSS_PENALTY if cross else 1.0)
        if best is None or tot > best[0] + 1e-9: best = (tot, a, cross)
    tot, a, cross = best
    return a, min(a + W, dur), float(tot), "cửa sổ heat lớn nhất" + (" (còn cắt ngang ranh giới cảnh)" if cross else "")

def sheet(v, out, frames, start=None, W=None, dur=None):
    if start is None:
        a = [FF, "-y", "-nostats", "-loglevel", "error", "-threads", "2", "-i", v, "-an",
             "-vf", f"fps={frames}/{dur},scale=240:-2,tile=6x{(frames+5)//6}", "-frames:v", "1", out]
    else:
        a = [FF, "-y", "-nostats", "-loglevel", "error", "-threads", "2", "-ss", f"{start:.3f}", "-i", v, "-an",
             "-vf", f"fps=3/{W},scale=240:-2,tile=4x1", "-frames:v", "1", out]
    run(a)

def analyse(video, window=4.0, w_motion=0.4):
    dur, has_a = probe(video); nb = max(1, int(np.ceil(dur / BIN)))
    au = audio_series(video, nb) if has_a else None
    mo, cuts = motion_series(video, nb)
    if au is not None: heat = (1 - w_motion) * mm(au) + w_motion * mm(mo)
    else: heat = mm(mo)
    still = mo.max() < NO_ACTION_MOTION and (au is None or au.max() - au.min() < NO_ACTION_AUDIO_LU)
    s, e, h, reason = pick(heat, cuts, dur, window)
    if still:
        s, e = 0.0, min(window, dur); reason = "no_action_content: ảnh tĩnh/giọng đều, dùng hook 0-W s"
    return dict(start_s=s, end_s=e, heat=round(h, 4), series_len=nb, bin_s=BIN, scene_cuts=cuts,
                has_audio=au is not None, motion_max=round(float(mo.max()), 4), reason=reason,
                heat_series=[round(float(x), 3) for x in heat]), dur

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--window", type=float, default=4)
    ap.add_argument("--w-motion", type=float, default=0.4); ap.add_argument("--out")
    ap.add_argument("--sheets", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args(); t0 = time.time()
    res, dur = analyse(a.video, a.window, a.w_motion)
    if not a.no_sheets:
        vid = os.path.splitext(os.path.basename(a.video))[0]
        sheet(a.video, os.path.join(a.sheets, f"{vid}_all.jpg"), 12, dur=dur)
        sheet(a.video, os.path.join(a.sheets, f"{vid}_pick.jpg"), 4, start=res["start_s"], W=res["end_s"] - res["start_s"])
    res["elapsed_s"] = round(time.time() - t0, 1)
    txt = json.dumps(res, ensure_ascii=False)
    if a.out: open(a.out, "w", encoding="utf-8").write(txt)
    print(txt.encode("ascii", "backslashreplace").decode())
main()
