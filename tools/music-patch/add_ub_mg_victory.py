# -*- coding: utf-8 -*-
"""给 UB / MG 补 per-world Victory（outro）。

现状
----
ZBT 有 12 条 `ZBT_<世界>_Victory`，UB / MG 只有一条通用 `UB_Victory` /
`MG_Victory`。Lose 三个家族都有 per-world，唯独 Victory 缺 —— 不对称。

音源其实一直在，只是没接进来：
    D:\\temp\\音乐补丁\\custom_music\\UB_Victory_<World>.mp3
    D:\\temp\\音乐补丁\\custom_music\\MG_Victory_<World>.mp3

覆盖 10 个世界（Beach/Cowboy/Dark/Dino/Eighties/Future/Iceage/Kongfu/
Lostcity/Pirate）。Egypt / Sky / Modern 没有源，按 ZBT 的做法由通用曲兜底
（`switch` 的 default 分支）。

命名沿用 ZBT 的规则：`<家族>_<世界缩写>_Victory`
    AE=Egypt PI=Pirate COW=Cowboy KF=Kongfu FF=Future DA=Dark
    BWB=Beach IC=Iceage LC=Lostcity SK=Sky JM=Dino MD=Modern

⚠️ 枚举铁律：枚举值必须等于 Musics 下标。
   现有 484 条（0..483），`MusicAmount=484`。
   新音轨一律**追加在 483 之后**，值 484..503，`MusicAmount` 抬到 504。
   绝不插在中间 —— 那会把后面所有音轨的索引整体错位。
"""
import io
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _console_utf8  # noqa: E402,F401

REPO = r"D:\git\pvzge_web"
SRC = r"D:\temp\音乐补丁\custom_music"
DOCS = os.path.join(REPO, "docs")
AUDIO_ROOT = os.path.join(DOCS, "audio", "Music", "inGame")
MANIFEST = os.path.join(DOCS, "audio", "manifest.json")
MUSICS = os.path.join(DOCS, "assets", "resources", "import", "0d", "0d4cac202.json")
JS = os.path.join(DOCS, "assets", "main", "index.js")
PROBE = r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffprobe.EXE"

# 源后缀 -> (世界缩写, WorldMusic 枚举名)
WORLD_MAP = [
    ("Pirate",   "PI",  "w.Pirate"),
    ("Cowboy",   "COW", "w.Cowboy"),
    ("Kongfu",   "KF",  "w.Kongfu"),
    ("Future",   "FF",  "w.Future"),
    ("Dark",     "DA",  "w.Dark"),
    ("Beach",    "BWB", "w.Beach"),
    ("Iceage",   "IC",  "w.Ice"),
    ("Lostcity", "LC",  "w.Lostcity"),
    ("Dino",     "JM",  "w.Dino"),
    ("Eighties", "Eighties", "w.Eighties"),
]

FAMILIES = [("UB", "MiniGame_A"), ("MG", "MiniGame_B")]


def dur(p):
    r = subprocess.run([PROBE, "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return -1.0


def build_tracks():
    """[(新音轨名, 源文件名, musicLength, 实测时长, 世界枚举)]"""
    out = []
    for fam, _ in FAMILIES:
        for src_suffix, abbr, wenum in WORLD_MAP:
            name = f"{fam}_{abbr}_Victory"
            src = f"{fam}_Victory_{src_suffix}.mp3"
            p = os.path.join(SRC, src)
            if not os.path.exists(p):
                print(f"  !! 缺源: {src}")
                continue
            d = dur(p)
            # 与既有 ZBT 一致：musicLength = 时长 - 0.05
            out.append((name, src, round(d - 0.05, 2), d, wenum))
    return out


def main(apply=False):
    tracks = build_tracks()
    print(f"待新增 {len(tracks)} 条")
    print()
    for n, s, ml, d, w in tracks:
        print(f"  {n:<22} <- {s:<28} musicLength={ml:<6} 实测={d:.2f}s  {w}")
    print()

    js = io.open(JS, encoding="utf-8", errors="replace").read()

    # ---- 前置检查 ----
    for n, *_ in tracks:
        if f"t[t.{n}=" in js:
            raise SystemExit(f"枚举已存在，中止: {n}")

    ENUM_ANCHOR = 't[t.VIC_Tutorial=483]="VIC_Tutorial",t[t.MusicAmount=484]="MusicAmount"'
    if js.count(ENUM_ANCHOR) != 1:
        raise SystemExit("枚举锚点不唯一，中止")

    UB_ANCHOR = ('if(a!=v.Victory||window.__mts!="MiniGame_A"){t.next=20;break}'
                 'u=A.UB_Victory,g=!1,s=1,t.next=270;break')
    MG_ANCHOR = ('if(a!=v.Victory||window.__mts!="MiniGame_B"){t.next=26;break}'
                 'u=A.MG_Victory,g=!1,s=1,t.next=270;break')
    for tag, a in (("UB", UB_ANCHOR), ("MG", MG_ANCHOR)):
        if js.count(a) != 1:
            raise SystemExit(f"{tag} 接线锚点不唯一，中止")

    if not apply:
        print("[dry-run] 加 --apply 执行")
        return 0

    # ---------- 1) 复制音频 ----------
    print("=== 1/5 复制音频 ===")
    copied = 0
    for name, src, ml, d, w in tracks:
        dst_dir = os.path.join(AUDIO_ROOT, name)
        dst = os.path.join(dst_dir, name + ".mp3")
        if os.path.exists(dst):
            continue
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(os.path.join(SRC, src), dst)
        copied += 1
    print(f"  新复制 {copied} 个")

    # ---------- 2) manifest ----------
    print()
    print("=== 2/5 manifest ===")
    data = open(MANIFEST, "rb").read()
    new_lines = []
    for name, *_ in tracks:
        key = "rk_" + name
        if ('"%s"' % key).encode() in data:
            continue
        rel = "Music/inGame/%s/%s.mp3" % (name, name)
        new_lines.append('  "%s": "%s"' % (key, rel))
    print(f"  待新增 {len(new_lines)} 个 key")
    if new_lines:
        close = data.rfind(b"\n}")
        head = data[:close].rstrip()
        body = head + b"," + b"".join(
            b"\n" + l.encode("utf-8") + b"," for l in new_lines[:-1])
        body += b"\n" + new_lines[-1].encode("utf-8")
        out = body + data[close:]
        json.loads(out.decode("utf-8"))
        open(MANIFEST, "wb").write(out)
        print("  已写入")

    # ---------- 3) Musics ----------
    print()
    print("=== 3/5 Musics ===")
    raw = io.open(MUSICS, encoding="utf-8", errors="replace").read()
    i = raw.find('{"name":"WorldMap"')
    start = raw.rfind("[", 0, i)
    depth = 0
    end = None
    for k in range(start, len(raw)):
        if raw[k] == "[":
            depth += 1
        elif raw[k] == "]":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    arr = json.loads(raw[start:end])
    exist = {e["name"] for e in arr}
    absent = [(n, ml) for n, _, ml, _, _ in tracks if n not in exist]
    print(f"  现有 {len(arr)} 条，待追加 {len(absent)} 条")

    if absent:
        def num(v):
            return str(int(v)) if float(v) == int(v) else repr(float(v))
        items = "".join(
            ',{"name":"%s","tauri":"rk_%s","musicLength":%s}' % (n, n, num(ml))
            for n, ml in absent)
        new_txt = raw[:end - 1] + items + raw[end - 1:]
        json.loads(new_txt[start:start + len(new_txt[start:end + len(items)])])
        io.open(MUSICS, "w", encoding="utf-8", newline="").write(new_txt)
        print("  已写入")

    # ---------- 4) 枚举 ----------
    print()
    print("=== 4/5 枚举 ===")
    base = 484
    parts = []
    for idx, (name, *_rest) in enumerate(tracks):
        v = base + idx
        parts.append('t[t.%s=%d]="%s"' % (name, v, name))
    new_amt = base + len(tracks)
    new_enum = ('t[t.VIC_Tutorial=483]="VIC_Tutorial",' + ",".join(parts)
                + ',t[t.MusicAmount=%d]="MusicAmount"' % new_amt)
    js = js.replace(ENUM_ANCHOR + ',t[t.MusicAmount=484]="MusicAmount"'
                    if False else ENUM_ANCHOR,
                    't[t.VIC_Tutorial=483]="VIC_Tutorial",' + ",".join(parts)
                    + ',t[t.MusicAmount=%d]="MusicAmount"' % new_amt, 1)
    print(f"  追加 {len(tracks)} 项，MusicAmount 484 -> {new_amt}")

    # ---------- 5) 接线 ----------
    print()
    print("=== 5/5 接线 ===")
    for fam, mts in FAMILIES:
        cases = "".join(
            'case %s:u=A.%s_%s_Victory;break;' % (w, fam, abbr)
            for _, abbr, w in WORLD_MAP)
        anchor = (f'if(a!=v.Victory||window.__mts!="{mts}"){{t.next='
                  + ("20" if fam == "UB" else "26") + f';break}}'
                  f'u=A.{fam}_Victory,g=!1,s=1,t.next=270;break')
        nxt = "20" if fam == "UB" else "26"
        new = (f'if(a!=v.Victory||window.__mts!="{mts}"){{t.next={nxt};break}}'
               f'switch(e){{{cases}default:u=A.{fam}_Victory}}'
               f'g=!1,s=1,t.next=270;break')
        js = js.replace(anchor, new, 1)
        print(f"  {fam}: 加 {len(WORLD_MAP)} 个 case + default")

    io.open(JS, "w", encoding="utf-8", newline="").write(js)
    print()
    print("已写入 index.js")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))