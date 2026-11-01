# -*- coding: utf-8 -*-
"""UB / MG per-world Victory 的完整性验证。

核心是项目铁律：**枚举值必须等于 Musics 下标**。
引擎用 bgms[i] 索引，错一位就取到别人的曲子。
"""
import io
import json
import os
import re
import sys

REPO = r"D:\git\pvzge_web"
DOCS = os.path.join(REPO, "docs")
JS = os.path.join(DOCS, "assets", "main", "index.js")
MUSICS = os.path.join(DOCS, "assets", "resources", "import", "0d", "0d4cac202.json")
MANIFEST = os.path.join(DOCS, "audio", "manifest.json")

fails = []


def ck(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


js = io.open(JS, encoding="utf-8", errors="replace").read()

print("=== 1. 读 Musics ===")
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
print(f"  Musics 共 {len(arr)} 条")

print()
print("=== 2. 枚举 / Musics 逐项对齐（铁律）===")
# ⚠️ index.js 里有很多枚举（PlantType / ZombieType ...），
#    不能拿全部 `t[t.X=N]` 当 Music 枚举 —— 只从 Musics 表反向查。
enum = {n: int(v) for n, v in re.findall(r"t\[t\.(\w+)=(\d+)\]", js)}
amount = int(re.search(r"t\[t\.MusicAmount=(\d+)\]", js).group(1))
music_enum = {e["name"]: enum.get(e["name"]) for e in arr}
print(f"  Musics {len(arr)} 条，MusicAmount = {amount}")
print(f"  其中能在枚举里找到的: {sum(1 for v in music_enum.values() if v is not None)}")

ck(amount == len(arr), f"MusicAmount({amount}) == Musics 条数({len(arr)})")

# 反向：Musics 里每个条目，枚举值必须等于它的下标
# ⚠️ 基线里本来就有一些没有枚举的音轨（PIANO_* / P1_Start_* 等），
#    那是上游遗留，不属于本次改动范围。这里只断言：本次没有**新增**缺枚举项。
#    基数按「总数 - 20」动态算 —— 三个分支条数不同（334 / 484）。
BASE_COUNT = len(arr) - 20
mismatch_all = [(idx, e["name"], enum.get(e["name"]))
                for idx, e in enumerate(arr) if enum.get(e["name"]) != idx]
mismatch_new = [m for m in mismatch_all if m[0] >= BASE_COUNT]
ck(not mismatch_new,
   f"新增的 20 条全部有正确枚举（{len(mismatch_new)} 处错位）")
for m in mismatch_new[:10]:
    print(f"        Musics[{m[0]}] = {m[1]}  但枚举 = {m[2]}")
print(f"  （基线遗留的无枚举音轨 {len(mismatch_all) - len(mismatch_new)} 条，属上游原有，未触碰）")

# 关键：新增这 20 条不能挤动任何既有音轨的下标
# （只查基线里**本来就有**枚举的音轨；基线就没有的那 106 条天然是 None，跳过）
shifted = [(idx, e["name"], enum.get(e["name"]))
           for idx, e in enumerate(arr[:BASE_COUNT])
           if enum.get(e["name"]) is not None and enum.get(e["name"]) != idx]
ck(not shifted, f"既有音轨的下标未被挤动（{len(shifted)} 处位移）")
for m in shifted[:5]:
    print(f"        Musics[{m[0]}] = {m[1]} 枚举 = {m[2]}")

print()
print("=== 3. 新增的 20 条 ===")
new_names = [n for n in enum if n.startswith(("UB_", "MG_")) and
             n.endswith("_Victory") and n not in ("UB_Victory", "MG_Victory")]
print(f"  新增 {len(new_names)} 条")
ck(len(new_names) == 20, "新增数量为 20（UB 10 + MG 10）")

base = len(arr) - 20
ck(all(enum[n] >= base for n in new_names),
   f"全部追加在末尾（下标 >= {base}）")

print()
print("=== 4. 每个新音轨：文件 / manifest / Musics ===")
man = json.load(io.open(MANIFEST, encoding="utf-8"))
for n in sorted(new_names):
    p = os.path.join(DOCS, "audio", "Music", "inGame", n, n + ".mp3")
    has_file = os.path.exists(p)
    mkey = "rk_" + n
    in_man = mkey in man
    idx = enum[n]
    in_tbl = arr[idx]["name"] == n and arr[idx].get("tauri") == mkey
    ok = has_file and in_man and in_tbl
    if not ok:
        ck(False, f"{n}: file={has_file} manifest={in_man} table={in_tbl}")
    else:
        print(f"     OK  {n:<22} idx={idx:<4} {os.path.getsize(p):>7,} B")
ck(all(os.path.exists(os.path.join(DOCS, "audio", "Music", "inGame", n, n + ".mp3"))
       and ("rk_" + n) in man and arr[enum[n]]["name"] == n
       for n in new_names), "20 条全部 文件+manifest+Musics 齐备")

print()
print("=== 5. 接线 ===")
for fam, mts in (("UB", "MiniGame_A"), ("MG", "MiniGame_B")):
    pat = f'if(a!=v.Victory||window.__mts!="{mts}")'
    j = js.find(pat)
    seg = js[j:j + 900] if j > 0 else ""
    has_switch = "switch(e){" in seg
    cases = len(re.findall(r"case w\.\w+:u=A\." + fam + r"_\w+_Victory", seg))
    has_default = f"default:u=A.{fam}_Victory" in seg
    ck(has_switch, f"{fam} 使用 switch(e) 按世界选曲")
    ck(cases == 10, f"{fam} 有 10 个 case（实际 {cases}）")
    ck(has_default, f"{fam} 保留 default -> 通用 {fam}_Victory")

print()
if fails:
    print(f"❌ {len(fails)} 项失败")
    sys.exit(1)
print("✅ UB / MG per-world Victory 接入验证通过")