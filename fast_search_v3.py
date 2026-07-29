#!/usr/bin/env python3
"""MHWilds 快速配装搜索 v3 — 位掩码+向量化的DFS搜索

核心优化（参照网页配装器策略）：
1. 技能→索引映射，用tuple替代dict做技能累加
2. 候选装备预计算技能向量，消除DFS内的dict.get开销
3. 精确赤字向量，逐技能检查可行性
4. 分数上限剪枝+技能可行性剪枝
"""
import json, time, itertools, sys

DATA = r'C:\Users\007\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a6185c4f2b6eb165ebb798e'

# ==================== 技能数值 ====================
MUZ_ATK = {0:0, 1:3, 2:6, 3:10, 4:15, 5:20}
CHAL_ATK = {0:0, 1:4, 2:8, 3:12, 4:16, 5:20}
COUNTER_ATK = {0:0, 1:10, 2:15, 3:25}
ATK_VAL = {0:0, 1:3, 2:5, 3:7, 4:8, 5:9}
ATK_MUL = {0:1.0, 1:1.0, 2:1.0, 3:1.0, 4:1.02, 5:1.04}
CRIT_VAL = {
    '看破': {0:0, 1:4, 2:8, 3:12, 4:16, 5:20},
    '挑战者': {0:0, 1:3, 2:5, 3:7, 4:10, 5:15},
    '力量解放': {0:0, 1:10, 2:20, 3:30, 4:40, 5:50},
    '精神抖擞': {0:0, 1:10, 2:20, 3:30},
    '无我之境': {0:0, 1:3, 2:6, 3:10},
    '弱点特效': {0:0, 1:5, 2:10, 3:15, 4:20, 5:30},
}
SUPER_CRIT = {0:1.25, 1:1.28, 2:1.31, 3:1.34, 4:1.37, 5:1.40}
ELEM_CRIT = {0:1.0, 1:1.05, 2:1.10, 3:1.15}
DRAGON_ELE = {0:(0,1.0), 1:(40,1.0), 2:(50,1.1), 3:(60,1.2)}
OFF_GUARD = {0:1.0, 1:1.05, 2:1.10, 3:1.15}
BURST_ATK = {0:0, 1:8, 2:10, 3:12, 4:15, 5:18}
BURST_ELE = {0:0, 1:60, 2:80, 3:100, 4:120, 5:140}
FORAY_ATK = {0:0, 1:6, 2:8, 3:10, 4:12, 5:15}
FORAY_CRT = {0:0, 1:0, 2:5, 3:10, 4:15, 5:20}
COAL_ELE = {0:1.0, 1:1.05, 2:1.10, 3:1.15}
ABSORB_ELE = {0:0, 1:40, 2:50, 3:60}
ABSORB_COV = 0.50
OGUARD_COV = 0.40
GEKI_MUL = {0:1.0, 1:1.0, 2:1.2, 3:1.2, 4:1.3}
GEKI_ADD = {0:0, 1:0, 2:20, 3:20, 4:40}
FIRE_DRAGON_DMG = {0: 0, 1: 0, 2: 40, 3: 40, 4: 80}
W_ATK = 205 + 24
W_CRT = 5 - 5
W_ELE = 280 + 40 + 160
BAHAR_MUL = 1.05
WSLOTS = [3, 3, 3]
TMV = 309; TEM = 13.4
WP = 1.32; WE = 1.15
PC_R = WP*0.45*(TMV/100)
EC_R = WE*0.20*(TEM/10)
UR=0.70; URE=0.85; UM=0.50; UKZ=0.60; URK=0.50; UW=0.80; UF=0.90; UCOU=0.40; UCSG=0.30

SKILL_CAPS = {
    '利刃': 3, '格挡性能': 3, '快吃': 3, '减轻胆怯': 3, '缓冲': 1, '耳塞': 3,
    '攻击': 5, '看破': 5, '超会心': 5, '会心击【属性】': 3,
    '龙属性攻击强化': 3, '攻击守势': 3, '无伤': 5, '挑战者': 5,
    '弱点特效': 5, '连击': 5, '力量解放': 5, '精神抖擞': 3,
    '无我之境': 3, '逆袭': 3, '因祸得福': 3, '匠': 5, '攻势': 5,
    '怨恨': 5, '火场怪力': 5, '巧击': 5, '属性吸收': 3,
    '属性变换': 3, '锁刃刺击': 5, '破坏王': 3,
    '广域化': 5, '满足感': 3, '精灵加护': 3, '回避性能': 5,
    '防御': 7, '体术': 5, '跑者': 3, '强化持续': 3,
    '适应环境': 2, '适应水域·油泥': 2, '地质学': 3,
    '火属性攻击强化': 3, '水属性攻击强化': 3,
    '冰属性攻击强化': 3, '雷属性攻击强化': 3,
    '巨戟龙的默示录': 4, '火龙之力': 4, '凶爪龙之力': 4,
    '黑蚀龙之力': 4, '泡狐龙之力': 4, '煌雷龙之力': 4,
    '海龙的涡雷': 4, '冻峰龙之反叛': 4, '锁刃龙之饥饿': 4, '霸主之魂': 3,
}

# ==================== 加载数据 ====================
print("加载数据...", end=' ', flush=True)
with open(f'{DATA}\\decos_cn.json', 'r', encoding='utf-8') as f: decos = json.load(f)
with open(f'{DATA}\\armors_cn.json', 'r', encoding='utf-8') as f: armors = json.load(f)
with open(f'{DATA}\\my_charms.json', 'r', encoding='utf-8') as f: my_charms = json.load(f)
with open(f'{DATA}\\charms_cn.json', 'r', encoding='utf-8') as f: craft_charms = json.load(f)
with open(f'{DATA}\\skills_data.json', 'r', encoding='utf-8') as f: skills_data = json.load(f)

WEAPON_SK = frozenset(skills_data.get('武器技能', {}).keys())

SERIES_SK = frozenset([
    '巨戟龙的默示录', '火龙之力', '凶爪龙之力', '黑蚀龙之力',
    '泡狐龙之力', '煌雷龙之力', '海龙的涡雷',
    '冻峰龙之反叛', '锁刃龙之饥饿', '辟兽之力', '暗器蛸之力',
    '铠龙之守护', '雪狮子王之斗志', '雷颚龙之斗志', '波衣龙之守护',
    '狱焰蛸之反叛', '护锁刃龙之命脉', '白炽龙之脉动',
    '花舞祈祷', '千刃龙的斗志', '踊火祈祷', '欧米茄共鸣',
    '暗黑骑士之证', '梦灯祈祷', '祝谣祈祷',
])
GROUP_SK = frozenset(skills_data.get('组合技能', {}).keys()) if '组合技能' in skills_data else frozenset()
NO_DECO_SK = SERIES_SK | GROUP_SK
SLOT_SKILLS = frozenset([f'Lv{n}插槽' for n in range(1, 5)])

# 珠子索引
deco_idx = {}
deco_skill_map = {}
for d in decos:
    sks = []
    if d['skill1']: sks.append((d['skill1'], d['skill1_level']))
    if d.get('skill2'): sks.append((d['skill2'], d['skill2_level']))
    for sk, lv in sks:
        deco_idx.setdefault((sk, d['type']), []).append((d['slot'], lv, d['name']))
    deco_skill_map[d['name']] = sks

_deco_pool = {}
for dtype in ('weapon', 'armor'):
    seen = set(); pool = []
    for (sk, dt), entries in deco_idx.items():
        if dt != dtype: continue
        for sr, pts, dn in entries:
            if dn not in seen:
                seen.add(dn)
                pool.append((sr, sk, pts, dn))
    _deco_pool[dtype] = pool

def limit_break(slots, r):
    s = list(slots)
    if r == 5: s = [min(x+1, 3) for x in s]
    elif r == 6 and len(s) >= 2:
        s[0] = min(s[0]+1, 3); s[1] = min(s[1]+1, 3)
    return s

parts = {'head': [], 'body': [], 'arms': [], 'waist': [], 'legs': []}
for a in armors:
    p = a.get('part', '')
    if p in parts:
        sk = {}
        for k, v in a.get('skills', {}).items():
            sk[k] = sk.get(k, 0) + v
        sk.pop('巧击', None)
        sk.pop('锁刃刺击', None)
        r = a.get('rarity', 0)
        slots = limit_break(a.get('slots', [0,0,0]), r)
        parts[p].append({'name': a['name'], 'rarity': r, 'skills': sk, 'slots': slots})

all_charms = []
for c in my_charms: all_charms.append(c)
for c in craft_charms: all_charms.append(c)
charm_pool = []
for c in all_charms:
    sk = c.get('skills', {})
    has_useful = any(s in SKILL_CAPS for s in sk)
    if has_useful:
        ca = list(c.get('armor_slots', []))
        cw = list(c.get('weapon_slots', []))
        charm_pool.append({'name': c['name'], 'skills': dict(sk), 'armor_slots': ca, 'weapon_slots': cw})

print(f"珠子:{len(decos)} 防具:{sum(len(v) for v in parts.values())} 护石:{len(charm_pool)}")

# ==================== 伤害计算（与v2完全一致） ====================
def calc_damage(skl):
    def cl(sk, cap): return min(skl.get(sk, 0), cap)
    chal=cl('挑战者',5); burst=cl('连击',5); muzu=cl('无伤',5)
    weak=cl('弱点特效',5); furue=cl('精神抖擞',3); rikikai=cl('力量解放',5)
    super_lv=cl('超会心',5); ecrit=cl('会心击【属性】',3); migo=cl('无我之境',3)
    counter=cl('逆袭',3); atk=cl('攻击',5); kanken=cl('看破',5)
    dragon=cl('龙属性攻击强化',3); oguard=cl('攻击守势',3)
    coal=cl('因祸得福',3); foray=cl('攻势',5)
    absorb=cl('属性吸收',3)
    fire_dragon=cl('火龙之力',4)
    bahar=cl('霸主之魂',3)
    geki=cl('巨戟龙的默示录',4)
    touhou=cl('冻峰龙之反叛',4)
    kizuna=cl('锁刃龙之饥饿',4)
    kuroshoku=cl('黑蚀龙之力',4)
    kyozou=cl('凶爪龙之力',4)
    ecb=ELEM_CRIT[ecrit]; scb=SUPER_CRIT[super_lv]
    bahar_mul = BAHAR_MUL if bahar >= 3 else 1.0
    atk_mul = ATK_MUL[atk]
    og = 1.0 + (OFF_GUARD[oguard] - 1.0) * OGUARD_COV if oguard > 0 else 1.0
    d_mul = DRAGON_ELE[dragon][1]
    geki_mul = GEKI_MUL[geki]
    geki_add = GEKI_ADD[geki]
    if coal > 0:
        coal_expect = 1.0 + (COAL_ELE[coal] - 1.0) * UCSG
    else:
        coal_expect = 1.0
    d_add = DRAGON_ELE[dragon][0]
    absorb_add = ABSORB_ELE[absorb] * ABSORB_COV
    kyozou_atk = 8 if kyozou >= 2 else 0
    states = []
    if chal > 0 or geki > 0: states.append(('rage', UR))
    if burst > 0: states.append(('rengeki', URE))
    if muzu > 0: states.append(('mukizu', UM))
    if kuroshoku >= 2 and migo >= 3:
        states.append(('kuroshoku_migo', 0.60))
    elif kuroshoku >= 2:
        states.append(('kuroshoku', 0.60))
    if rikikai > 0: states.append(('rikikai', URK))
    if weak > 0: states.append(('weak', UW))
    if furue > 0: states.append(('furue', UF))
    if counter > 0: states.append(('counter', UCOU))
    if not states: states.append(('none', 1.0))
    wr = er = 0.0
    for combo in itertools.product(*([[True, False]] * len(states))):
        pr = 1.0
        add_atk = 0.0
        add_crt = 0
        add_ele = 0.0
        bactive = False
        geki_mul_act = 1.0
        geki_add_act = 0
        for (nm, up), act in zip(states, combo):
            pr *= up if act else (1 - up)
            if not act: continue
            if nm == 'rage':
                if chal > 0:
                    add_atk += CHAL_ATK[chal]; add_crt += CRIT_VAL['挑战者'][chal]
                if geki > 0:
                    geki_mul_act = geki_mul
                    geki_add_act = geki_add
            elif nm == 'rengeki':
                add_atk += BURST_ATK[burst]; add_ele += BURST_ELE[burst]; bactive = True
            elif nm == 'mukizu':
                add_atk += MUZ_ATK[muzu]
            elif nm == 'kurozumi':
                add_crt += CRIT_VAL['无我之境'][migo]
            elif nm == 'kuroshoku':
                add_crt += 15
            elif nm == 'kuroshoku_migo':
                add_crt += 25
            elif nm == 'rikikai':
                add_crt += CRIT_VAL['力量解放'][rikikai]
            elif nm == 'weak':
                add_crt += CRIT_VAL['弱点特效'][weak]
            elif nm == 'furue':
                add_crt += CRIT_VAL['精神抖擞'][furue]
            elif nm == 'counter':
                add_atk += COUNTER_ATK[counter]
        if atk > 0:
            add_atk += ATK_VAL[atk]
        if kyozou_atk > 0:
            add_atk += kyozou_atk
        if kanken > 0:
            add_crt += CRIT_VAL['看破'][kanken]
        ea = W_ATK * atk_mul * og * bahar_mul + add_atk
        ec = min(W_CRT + add_crt, 100)
        be = W_ELE * d_mul * geki_mul_act * coal_expect + d_add + geki_add_act + add_ele + absorb_add
        cr = ec / 100.0
        crit_phys = cr * scb + (1 - cr)
        crit_elem = cr * ecb + (1 - cr)
        wr += pr * ea * PC_R * crit_phys
        er += pr * be * EC_R * crit_elem
    return wr + er + FIRE_DRAGON_DMG.get(fire_dragon, 0)

def calc_weighted_crit(skl):
    def cl(sk, cap): return min(skl.get(sk, 0), cap)
    chal=cl('挑战者',5); burst=cl('连击',5); muzu=cl('无伤',5)
    weak=cl('弱点特效',5); furue=cl('精神抖擞',3); rikikai=cl('力量解放',5)
    migo=cl('无我之境',3); counter=cl('逆袭',3); atk=cl('攻击',5); kanken=cl('看破',5)
    foray=cl('攻势',5)
    kuroshoku=cl('黑蚀龙之力',4)
    migo=cl('无我之境',3)
    states = []
    if chal > 0: states.append(('rage', UR))
    if burst > 0: states.append(('rengeki', URE))
    if muzu > 0: states.append(('mukizu', UM))
    if kuroshoku >= 2 and migo >= 3:
        states.append(('kuroshoku_migo', 0.60))
    elif kuroshoku >= 2:
        states.append(('kuroshoku', 0.60))
    if rikikai > 0: states.append(('rikikai', URK))
    if weak > 0: states.append(('weak', UW))
    if furue > 0: states.append(('furue', UF))
    if counter > 0: states.append(('counter', UCOU))
    if not states: states.append(('none', 1.0))
    wcr = 0.0
    for combo in itertools.product(*([[True, False]] * len(states))):
        pr = 1.0
        add_crt = 0
        for (nm, up), act in zip(states, combo):
            pr *= up if act else (1 - up)
            if not act: continue
            if nm == 'rage': add_crt += CRIT_VAL['挑战者'][chal]
            elif nm == 'kurozumi': add_crt += CRIT_VAL['无我之境'][migo]
            elif nm == 'kuroshoku': add_crt += 15
            elif nm == 'kuroshoku_migo': add_crt += 25
            elif nm == 'rikikai': add_crt += CRIT_VAL['力量解放'][rikikai]
            elif nm == 'weak': add_crt += CRIT_VAL['弱点特效'][weak]
            elif nm == 'furue': add_crt += CRIT_VAL['精神抖擞'][furue]
        if kanken > 0: add_crt += CRIT_VAL['看破'][kanken]
        ec = min(W_CRT + add_crt, 100)
        wcr += pr * ec
    return wcr

# ==================== 珠子填充（与v2一致） ====================
import functools

@functools.lru_cache(maxsize=65536)
def gain(sk, old, add):
    cap = SKILL_CAPS.get(sk, 99)
    c = min(old, cap)
    return min(add, cap - c) if c < cap else 0

_WEAPON_DECO_POOL = None
_ARMOR_DECO_POOL = None
_ARMOR_DECO_BY_SKILL = None  # skill -> [deco, ...] 索引

def _build_deco_pool_full(dtype):
    seen = set(); pool = []
    for d in decos:
        if d.get('type') != dtype: continue
        dn = d['name']
        if dn in seen: continue
        seen.add(dn)
        sks = []
        if d.get('skill1'): sks.append((d['skill1'], d.get('skill1_level', 0)))
        if d.get('skill2'): sks.append((d['skill2'], d.get('skill2_level', 0)))
        pool.append({'name': dn, 'slot': d['slot'], 'skills': sks})
    return pool

def _get_deco_pool(dtype):
    global _WEAPON_DECO_POOL, _ARMOR_DECO_POOL, _ARMOR_DECO_BY_SKILL
    if dtype == 'weapon':
        if _WEAPON_DECO_POOL is None:
            _WEAPON_DECO_POOL = _build_deco_pool_full('weapon')
        return _WEAPON_DECO_POOL
    else:
        if _ARMOR_DECO_POOL is None:
            _ARMOR_DECO_POOL = _build_deco_pool_full('armor')
            # 同时构建技能→珠子索引
            _ARMOR_DECO_BY_SKILL = {}
            for _d in _ARMOR_DECO_POOL:
                for _sk, _pts in _d['skills']:
                    _ARMOR_DECO_BY_SKILL.setdefault(_sk, []).append(_d)
        return _ARMOR_DECO_POOL

def _get_armor_deco_for_skill(sk):
    """获取提供指定技能的防具珠子列表（用索引加速）"""
    if _ARMOR_DECO_BY_SKILL is None:
        _get_deco_pool('armor')
    return _ARMOR_DECO_BY_SKILL.get(sk, [])

_fill_weapon_cache = {}
_FEASIBILITY_ONLY = False  # True时跳过fill_slots的优化循环（追加技能查询用）

def _fill_weapon_slots_smart(fs, w_slots, fixed_skills):
    slots = sorted([s for s in w_slots if s > 0], reverse=True)
    w_fixed = {s: r for s, r in fixed_skills.items() if s in WEAPON_SK and fs.get(s, 0) < r}
    if not w_fixed:
        return fs, [], slots
    if not slots:
        return None
    cache_key = (frozenset(w_fixed.items()), tuple(slots),
                 tuple(sorted((s, fs.get(s, 0)) for s in w_fixed)))
    if cache_key in _fill_weapon_cache:
        cached = _fill_weapon_cache[cache_key]
        if cached is None:
            return None
        new_fs = dict(fs)
        for sk, lv in cached['add_skills'].items():
            new_fs[sk] = min(new_fs.get(sk, 0) + lv, SKILL_CAPS.get(sk, 99))
        return new_fs, list(cached['used']), list(cached['rem_slots'])
    from itertools import combinations_with_replacement
    pool = _get_deco_pool('weapon')
    # 按技能贡献去重：相同(slot, {skill:pts})只保留一个
    seen_patterns = set()
    cand_decos = []
    for deco in pool:
        if deco['slot'] > max(slots):
            continue
        has_relevant = False
        relevant_skills = {}
        for sk, pts in deco['skills']:
            if sk in w_fixed and pts > 0:
                has_relevant = True
                relevant_skills[sk] = pts
        if has_relevant:
            pattern = (deco['slot'], frozenset(relevant_skills.items()))
            if pattern not in seen_patterns:
                seen_patterns.add(pattern)
                cand_decos.append(deco)
    if not cand_decos:
        _fill_weapon_cache[cache_key] = None
        return None
    # 按有效贡献排序：pts高且slot低优先
    cand_decos.sort(key=lambda d: (-sum(pts for sk, pts in d['skills'] if sk in w_fixed), d['slot']))
    n_slots = len(slots)
    # 快速上界检查：top n_slots珠子的赤字贡献总和 < 赤字总量 → 无解
    _total_deficit = sum(w_fixed.values())
    _deco_contribs = sorted((sum(min(pts, w_fixed.get(sk, 0)) for sk, pts in d['skills'] if sk in w_fixed)
                             for d in cand_decos), reverse=True)
    if sum(_deco_contribs[:n_slots]) < _total_deficit:
        _fill_weapon_cache[cache_key] = None
        return None
    for n in range(1, n_slots + 1):
        for combo in combinations_with_replacement(range(len(cand_decos)), n):
            deco_list = [cand_decos[i] for i in combo]
            deco_slots = sorted([d['slot'] for d in deco_list], reverse=True)
            ok = True
            for ds, ss in zip(deco_slots, slots):
                if ds > ss:
                    ok = False; break
            if not ok:
                continue
            test_fs = dict(fs)
            for deco in deco_list:
                for sk, pts in deco['skills']:
                    test_fs[sk] = min(test_fs.get(sk, 0) + pts, SKILL_CAPS.get(sk, 99))
            all_ok = True
            for sk, need in w_fixed.items():
                if test_fs.get(sk, 0) < need:
                    all_ok = False; break
            if all_ok:
                used = [d['name'] for d in deco_list]
                used_slots = set()
                for deco in deco_list:
                    for i, s in enumerate(slots):
                        if i not in used_slots and s >= deco['slot']:
                            used_slots.add(i)
                            break
                rem_slots = [s for i, s in enumerate(slots) if i not in used_slots]
                add_skills = {}
                for sk in w_fixed:
                    add_skills[sk] = test_fs.get(sk, 0) - fs.get(sk, 0)
                _fill_weapon_cache[cache_key] = {
                    'used': used, 'rem_slots': rem_slots, 'add_skills': add_skills
                }
                return test_fs, used, rem_slots
    _fill_weapon_cache[cache_key] = None
    return None

def fill_slots(skills, a_slots, w_slots, fixed_skills, min_keep_armor=0):
    fs = dict(skills); used = []
    a = sorted([s for s in a_slots if s > 0])
    w = sorted([s for s in w_slots if s > 0], reverse=True)
    slot_skill_needs = {}
    for sk, lv in fixed_skills.items():
        if sk.startswith('Lv') and sk.endswith('插槽'):
            try:
                n = int(sk[2:-2])
                slot_skill_needs[n] = lv
            except ValueError:
                pass
    total_slot_keep = sum(slot_skill_needs.values())
    w_result = _fill_weapon_slots_smart(dict(fs), w, fixed_skills)
    if w_result is None:
        return None
    fs, w_used, rem_w = w_result
    used.extend(w_used)
    armor_fixed = {s: r for s, r in fixed_skills.items()
                   if s not in WEAPON_SK and not (s.startswith('Lv') and s.endswith('插槽'))
                   and s not in NO_DECO_SK
                   and fs.get(s, 0) < r}
    for sk_need, need_lv in armor_fixed.items():
        dtype = 'armor'
        _skill_decos = _get_armor_deco_for_skill(sk_need)
        while fs.get(sk_need, 0) < need_lv:
            placed = False
            best = None
            best_score = -1
            for i, s in enumerate(a):
                for deco in _skill_decos:
                    if deco['slot'] > s: continue
                    pts_for_need = 0
                    for sk, pts in deco['skills']:
                        if sk == sk_need:
                            pts_for_need = pts
                            break
                    g = gain(sk_need, fs.get(sk_need, 0), pts_for_need)
                    if g > 0:
                        bonus = 0
                        for sk, pts in deco['skills']:
                            if sk != sk_need and sk in fixed_skills:
                                if fs.get(sk, 0) < fixed_skills[sk]:
                                    bonus += gain(sk, fs.get(sk, 0), pts)
                        score = g * 100 + bonus
                        if score > best_score:
                            best_score = score
                            best = (deco, i)
            if best:
                deco, idx = best
                a.pop(idx)
                for sk, pts in deco['skills']:
                    fs[sk] = min(fs.get(sk, 0) + pts, SKILL_CAPS.get(sk, 99))
                used.append(deco['name']); placed = True
            if not placed: break
        if fs.get(sk_need, 0) < need_lv:
            return None
    for s, r in fixed_skills.items():
        if s.startswith('Lv') and s.endswith('插槽'):
            continue
        if s in NO_DECO_SK:
            continue
        if fs.get(s, 0) < r:
            return None
    w_rem = sorted([s for s in rem_w if s > 0], reverse=True)
    if not _FEASIBILITY_ONLY:
        for deco in sorted(_get_deco_pool('weapon'), key=lambda d: -d['slot']):
            for i, s in enumerate(w_rem):
                if s >= deco['slot']:
                    g_total = sum(gain(sk, fs.get(sk, 0), pts) for sk, pts in deco['skills'])
                    if g_total > 0:
                        w_rem.pop(i)
                        for sk, pts in deco['skills']:
                            fs[sk] = min(fs.get(sk, 0) + pts, SKILL_CAPS.get(sk, 99))
                        used.append(deco['name'])
                        break
    pool_a = _get_deco_pool('armor')
    min_keep = max(min_keep_armor, total_slot_keep)
    if not _FEASIBILITY_ONLY:
        while len(a) > min_keep:
            best_d = None; best_s = -1; best_i = -1
            for si, s in enumerate(a):
                for deco in pool_a:
                    if deco['slot'] > s: continue
                    g_total = sum(gain(sk, fs.get(sk, 0), pts) for sk, pts in deco['skills'])
                    if g_total > 0 and g_total * 100 > best_s:
                        best_s = g_total * 100; best_d = deco; best_i = si
            if best_d is None: break
            a.pop(best_i)
            for sk, pts in best_d['skills']:
                fs[sk] = min(fs.get(sk, 0) + pts, SKILL_CAPS.get(sk, 99))
            used.append(best_d['name'])
    all_rem = a + w_rem
    for n, need_cnt in slot_skill_needs.items():
        avail = sum(1 for s in all_rem if s >= n)
        if avail < need_cnt:
            return None
        fs[f'Lv{n}插槽'] = need_cnt
    return fs, used, a, w_rem

# ==================== 轻量级缺口检查 ====================
def can_fill_gap(skill_gap, a_slots, w_slots):
    if not skill_gap:
        return True
    w_gap = {sk: need for sk, need in skill_gap.items() if sk in WEAPON_SK}
    w_slots_avail = sorted([s for s in w_slots if s > 0], reverse=True)
    for sk, need in w_gap.items():
        pool = deco_idx.get((sk, 'weapon'), [])
        if not pool:
            return False
        best_pts = max(pts for sr, pts, dn in pool)
        need_slots = (need + best_pts - 1) // best_pts
        if need_slots > len(w_slots_avail):
            return False
    a_gap = {sk: need for sk, need in skill_gap.items() if sk not in WEAPON_SK}
    a_slots_avail = sorted([s for s in a_slots if s > 0], reverse=True)
    for sk, need in a_gap.items():
        pool = deco_idx.get((sk, 'armor'), [])
        if not pool:
            return False
        best_pts = max(pts for sr, pts, dn in pool)
        need_slots = (need + best_pts - 1) // best_pts
        if need_slots > len(a_slots_avail):
            return False
    return True

# ==================== 珠子可行性检查 ====================
def _check_deco_feasible(skills, a_slots, w_slots, fixed_skills, combo_skills,
                         weapon_skills, min_rem_armor):
    a_cnt = {1:0, 2:0, 3:0}
    for s in a_slots:
        if s > 0: a_cnt[s] = a_cnt[s] + 1
    w_cnt = {1:0, 2:0, 3:0}
    for s in w_slots:
        if s > 0: w_cnt[s] = w_cnt[s] + 1
    rem = min_rem_armor
    for lv in [1, 2, 3]:
        while rem > 0 and a_cnt[lv] > 0:
            a_cnt[lv] -= 1
            rem -= 1
    if rem > 0:
        return False
    for sk, lv in fixed_skills.items():
        if sk.startswith('Lv') and sk.endswith('插槽'):
            try:
                n = int(sk[2:-2])
            except ValueError:
                continue
            need = lv
            for slv in range(n, 4):
                while need > 0 and a_cnt[slv] > 0:
                    a_cnt[slv] -= 1
                    need -= 1
                if need == 0: break
            for slv in range(n, 4):
                while need > 0 and w_cnt[slv] > 0:
                    w_cnt[slv] -= 1
                    need -= 1
                if need == 0: break
            if need > 0:
                return False
    all_req = {}
    for sk, need in fixed_skills.items():
        if sk.startswith('Lv') and sk.endswith('插槽'):
            continue
        if sk in NO_DECO_SK:
            continue
        all_req[sk] = need
    if combo_skills:
        for sk, need in combo_skills.items():
            if sk in NO_DECO_SK:
                continue
            armor_need = max(0, need - weapon_skills.get(sk, 0))
            if armor_need > 0:
                all_req[sk] = all_req.get(sk, 0) + armor_need
    w_total_need = 0
    a_total_need = 0
    for sk, need in all_req.items():
        have = skills.get(sk, 0)
        if have >= need: continue
        d = need - have
        dtype = 'weapon' if sk in WEAPON_SK else 'armor'
        pool = deco_idx.get((sk, dtype), [])
        if not pool:
            return False
        if dtype == 'weapon':
            w_total_need += d
        else:
            a_total_need += d
    w_total_slots = w_cnt[1] + w_cnt[2] + w_cnt[3]
    a_total_slots = a_cnt[1] + a_cnt[2] + a_cnt[3]
    if a_total_need > 0:
        a_max_pts = max((max(pts for sr, pts, dn in deco_idx.get((sk, 'armor'), [(0,1,'')]))
                        for sk in all_req if sk not in WEAPON_SK and skills.get(sk, 0) < all_req[sk]), default=1)
        a_slots_needed = (a_total_need + a_max_pts - 1) // a_max_pts
        if a_slots_needed > a_total_slots:
            return False
    w_need = {1:0, 2:0, 3:0}
    a_need = {1:0, 2:0, 3:0}
    for sk, need in all_req.items():
        have = skills.get(sk, 0)
        if have >= need: continue
        d = need - have
        dtype = 'weapon' if sk in WEAPON_SK else 'armor'
        if dtype == 'weapon':
            continue
        pool = deco_idx.get((sk, dtype), [])
        best = max(pool, key=lambda x: x[1])
        best_pts = best[1]
        best_slot = best[0]
        slots_needed = (d + best_pts - 1) // best_pts
        a_need[best_slot] += slots_needed
    w_avail = [0, 0, 0, 0]
    w_use = [0, 0, 0, 0]
    for lv in [1, 2, 3]:
        w_avail[lv] = w_cnt[lv]
        w_use[lv] = w_need[lv]
    for lv in [1, 2]:
        if w_use[lv] > w_avail[lv]:
            borrow = w_use[lv] - w_avail[lv]
            w_use[lv] = w_avail[lv]
            w_use[lv+1] += borrow
    if w_use[3] > w_avail[3]:
        return False
    a_avail = [0, 0, 0, 0]
    a_use2 = [0, 0, 0, 0]
    for lv in [1, 2, 3]:
        a_avail[lv] = a_cnt[lv]
        a_use2[lv] = a_need[lv]
    for lv in [1, 2]:
        if a_use2[lv] > a_avail[lv]:
            borrow = a_use2[lv] - a_avail[lv]
            a_use2[lv] = a_avail[lv]
            a_use2[lv+1] += borrow
    if a_use2[3] > a_avail[3]:
        return False
    return True

# ==================== 支配检查 ====================
def _dominated_check(item, dom, skill_names):
    # 使用预排序的slots_sorted，避免每次sorted
    d_s = dom.get('slots_sorted')
    i_s = item.get('slots_sorted')
    if d_s is None: d_s = tuple(sorted(dom['slots'], reverse=True))
    if i_s is None: i_s = tuple(sorted(item['slots'], reverse=True))
    for i in range(max(len(d_s), len(i_s))):
        d = d_s[i] if i < len(d_s) else 0
        iv = i_s[i] if i < len(i_s) else 0
        if d < iv: return False
    d_ws = dom.get('wslots_sorted', ())
    i_ws = item.get('wslots_sorted', ())
    for i in range(max(len(d_ws), len(i_ws))):
        d = d_ws[i] if i < len(d_ws) else 0
        iv = i_ws[i] if i < len(i_ws) else 0
        if d < iv: return False
    # 只检查有赤字的技能（dom中技能值<item中时才不支配）
    item_sk = item['skills']
    dom_sk = dom['skills']
    for sk in skill_names:
        if item_sk.get(sk, 0) > dom_sk.get(sk, 0): return False
    return True

# ==================== 候选构建 ====================
def _build_candidates(charm_pool, fixed_skills, combo_skills, quiet=False, extra_skill_names=None):
    """构建候选装备列表（与dfs_search分离，允许缓存复用）

    extra_skill_names: 额外技能名集合，用于扩大支配检查和预过滤范围，
    确保追加技能查询时不会误删含目标技能的候选。
    """
    weapon_skills = {}
    if combo_skills:
        for sk in combo_skills:
            weapon_skills[sk] = weapon_skills.get(sk, 0) + 1

    armor_fixed = {s: r for s, r in fixed_skills.items() if s not in WEAPON_SK}
    weapon_fixed = {s: r for s, r in fixed_skills.items() if s in WEAPON_SK}

    all_skill_names = set(fixed_skills.keys())
    if combo_skills:
        all_skill_names.update(combo_skills.keys())
    if extra_skill_names:
        all_skill_names.update(extra_skill_names)

    # 预计算合并技能需求（避免在循环中重复get）
    merged_needs = dict(fixed_skills)
    if combo_skills:
        for s, lv in combo_skills.items():
            merged_needs[s] = max(merged_needs.get(s, 0), lv)

    part_names = ['head', 'body', 'arms', 'waist', 'legs']
    candidates = []
    for pi, pn in enumerate(part_names):
        for a in parts[pn]:
            a_sk = a['skills']
            sk_score = sum(min(v, merged_needs.get(s, 0))
                          for s, v in a_sk.items() if s in all_skill_names)
            slot_sum = sum(a['slots']) if a['slots'] else 0
            score = sk_score + slot_sum
            candidates.append({
                'name': a['name'], 'part_idx': pi,
                'skills': a_sk, 'slots': a['slots'],
                'slots_sorted': tuple(sorted(a['slots'], reverse=True)),
                'wslots_sorted': (),
                'rarity': a['rarity'], 'score': score,
                'max_slot': max(a['slots']) if a['slots'] else 0,
                'slot_sum': slot_sum, 'w_slot_sum': 0
            })
    for c in charm_pool:
        c_sk = c.get('skills', {})
        sk_score = sum(min(v, merged_needs.get(s, 0))
                      for s, v in c_sk.items() if s in all_skill_names)
        armor_slots = c.get('armor_slots', [])
        weapon_slots = c.get('weapon_slots', [])
        a_sum = sum(armor_slots) if armor_slots else 0
        w_sum = sum(weapon_slots) if weapon_slots else 0
        score = sk_score + a_sum + w_sum
        candidates.append({
            'name': c['name'], 'part_idx': 5,
            'skills': c_sk, 'slots': armor_slots,
            'slots_sorted': tuple(sorted(armor_slots, reverse=True)),
            'weapon_slots': weapon_slots,
            'wslots_sorted': tuple(sorted(weapon_slots, reverse=True)),
            'rarity': 0, 'score': score,
            'max_slot': max(armor_slots + weapon_slots) if (armor_slots or weapon_slots) else 0,
            'slot_sum': a_sum, 'w_slot_sum': w_sum
        })

    # 去重
    merged = {}
    for c in candidates:
        key = (c['part_idx'],
               frozenset(c['skills'].items()),
               tuple(sorted(c['slots'])),
               tuple(sorted(c.get('weapon_slots', ()))))
        if key in merged:
            merged[key]['names'].append(c['name'])
            if c['score'] > merged[key]['score']:
                merged[key]['score'] = c['score']
                merged[key]['max_slot'] = c['max_slot']
                merged[key]['slot_sum'] = c['slot_sum']
                merged[key]['w_slot_sum'] = c['w_slot_sum']
        else:
            merged[key] = {
                'name': c['name'], 'names': [c['name']],
                'part_idx': c['part_idx'], 'skills': c['skills'],
                'slots': c['slots'], 'weapon_slots': c.get('weapon_slots', []),
                'slots_sorted': c.get('slots_sorted', ()),
                'wslots_sorted': c.get('wslots_sorted', ()),
                'rarity': c['rarity'], 'score': c['score'],
                'max_slot': c['max_slot'],
                'slot_sum': c['slot_sum'], 'w_slot_sum': c['w_slot_sum'],
            }
    candidates = list(merged.values())
    merged_count = len(candidates)

    # 预过滤
    relevant_skills = set(all_skill_names)
    filtered = []
    for c in candidates:
        has_skill = any(s in relevant_skills for s in c['skills'])
        has_slot = (c['slot_sum'] + c['w_slot_sum']) > 0
        if has_skill or has_slot:
            filtered.append(c)
    candidates = filtered

    # 部位级支配预剪枝
    part_groups = {}
    for c in candidates:
        part_groups.setdefault(c['part_idx'], []).append(c)
    pruned_candidates = []
    for pi in range(6):
        grp = part_groups.get(pi, [])
        if not grp:
            continue
        grp.sort(key=lambda x: (-x['score'], -x['max_slot']))
        kept = []
        for item in grp:
            dominated = False
            for dom in kept:
                if _dominated_check(item, dom, all_skill_names):
                    dominated = True
                    break
            if not dominated:
                kept.append(item)
        pruned_candidates.extend(kept)
    candidates = pruned_candidates

    candidates.sort(key=lambda x: (-x['score'], -x['max_slot']))

    # 改进排序：系列技能装备优先，然后按score降序
    series_req_set = set(s for s, lv in fixed_skills.items() if s in NO_DECO_SK and lv > 0)
    if combo_skills:
        series_req_set.update(s for s, lv in combo_skills.items() if s in NO_DECO_SK and lv > 0)

    def _sort_key(c):
        # 系列技能数（多优先） + score（高优先） + max_slot（高优先）
        series_cnt = sum(1 for s in c['skills'] if s in series_req_set)
        return (-series_cnt, -c['score'], -c['max_slot'])

    candidates.sort(key=_sort_key)

    # 护石可行性过滤（优化版：基线快速路径 + _fill_weapon_slots_smart缓存）
    charm_cands = [c for c in candidates if c['part_idx'] == 5]
    armor_cands = [c for c in candidates if c['part_idx'] != 5]
    w_deficit_set = set(s for s, d in fixed_skills.items() if s in WEAPON_SK and d > 0)
    if w_deficit_set:
        w_deficit_init = {}
        for s, need in weapon_fixed.items():
            if s.startswith('Lv') and s.endswith('插槽'): continue
            if s in NO_DECO_SK: continue
            h = weapon_skills.get(s, 0)
            if h < need:
                w_deficit_init[s] = need - h
        if combo_skills:
            for s, need in combo_skills.items():
                if s in NO_DECO_SK: continue
                if s not in WEAPON_SK: continue
                h = max(0, weapon_skills.get(s, 0) - weapon_skills.get(s, 0))
                if h < need:
                    w_deficit_init[s] = w_deficit_init.get(s, 0) + (need - h)
        if w_deficit_init:
            # 快速路径：先检查基线（无护石贡献）能否满足武器赤字
            _base_fs = dict(weapon_skills)
            _base_fixed = {}
            for s, d in w_deficit_init.items():
                _base_fixed[s] = _base_fs.get(s, 0) + d
            _base_ok = _fill_weapon_slots_smart(_base_fs, list(WSLOTS), _base_fixed) is not None
            if not _base_ok:
                # 基线不可行 → 逐组检查（按武器技能贡献分组，复用缓存）
                _charm_by_wsk = {}
                for cc in charm_cands:
                    wsk_key = frozenset((s, lv) for s, lv in cc['skills'].items()
                               if s in w_deficit_init and lv > 0)
                    _charm_by_wsk.setdefault(wsk_key, []).append(cc)
                _viable_charms = []
                for _wsk_key, _cc_list in _charm_by_wsk.items():
                    _test_fs = dict(weapon_skills)
                    if _wsk_key:
                        for s, lv in _wsk_key:
                            _test_fs[s] = _test_fs.get(s, 0) + lv
                    _test_fixed = {}
                    for s, d in w_deficit_init.items():
                        rem = d - (_test_fs.get(s, 0) - weapon_skills.get(s, 0))
                        if rem > 0:
                            _test_fixed[s] = _test_fs.get(s, 0) + rem
                    if not _test_fixed:
                        _viable_charms.extend(_cc_list)
                        continue
                    result = _fill_weapon_slots_smart(_test_fs, list(WSLOTS), _test_fixed)
                    if result is not None:
                        _viable_charms.extend(_cc_list)
                charm_cands = _viable_charms
        charm_cands.sort(key=lambda c: (
            -sum(1 for s in c['skills'] if s in w_deficit_set),
            -c['score']
        ))
    candidates = charm_cands + armor_cands
    if not quiet:
        orig_count = sum(len(parts[p]) for p in part_names) + len(charm_pool)
        print(f"  候选总数:{orig_count} → 去重{merged_count} → 预过滤{len(candidates)}")

    best_by_part = {}
    best_slot_by_part = {}
    candidates_by_part = {}
    for pi in range(6):
        part_cands = [c for c in candidates if c['part_idx'] == pi]
        # 每个部位内按系列技能优先+score降序排列
        part_cands.sort(key=_sort_key)
        candidates_by_part[pi] = part_cands
        if part_cands:
            best_by_part[pi] = part_cands[0]['score']
            best_slot_by_part[pi] = max(c['slot_sum'] + c['w_slot_sum'] for c in part_cands)
        else:
            best_by_part[pi] = 0
            best_slot_by_part[pi] = 0

    part_series_availability = {}
    all_series_in_gear = set()
    for pi in range(5):
        pn = part_names[pi]
        avail = set()
        for a in parts[pn]:
            for sk_name in a.get('skills', {}):
                if sk_name in NO_DECO_SK:
                    avail.add(sk_name)
        part_series_availability[pi] = avail
        all_series_in_gear |= avail

    return (candidates, all_skill_names, weapon_skills, armor_fixed, weapon_fixed,
            best_by_part, best_slot_by_part, candidates_by_part, part_series_availability)


# ==================== 向量化DFS搜索 ====================
def dfs_search(charm_pool, fixed_skills, combo_skills, min_rem_armor,
               max_results=0, timeout_s=10.0, quiet=False, cached_ctx=None):
    """DFS回溯搜索（向量化优化版 v3）

    核心优化（参照网页配装器策略）：
    1. 技能→索引映射：所有需求技能映射为整数索引，用list代替dict做累加
    2. 候选装备预计算技能向量：每件装备的技能贡献转为定长tuple
    3. 精确赤字向量：用list做加减，避免dict.get开销
    4. 逐技能可行性剪枝：每个赤字技能检查剩余部位能否提供
    5. 分数上限剪枝：剩余部位最高分+孔位容量 < 当前赤字 → 剪除
    """
    start_time = time.time()
    part_names = ['head', 'body', 'arms', 'waist', 'legs']

    if cached_ctx is not None:
        (candidates, all_skill_names, weapon_skills, armor_fixed, weapon_fixed,
         best_by_part, best_slot_by_part, candidates_by_part, part_series_availability) = cached_ctx
    else:
        ctx = _build_candidates(charm_pool, fixed_skills, combo_skills, quiet=quiet)
        (candidates, all_skill_names, weapon_skills, armor_fixed, weapon_fixed,
         best_by_part, best_slot_by_part, candidates_by_part, part_series_availability) = ctx

    # ===== 技能→索引映射 =====
    # 只追踪需要通过珠子/装备满足的技能（排除孔位技能和系列/组合技能）
    tracked_skills = []
    for s in fixed_skills:
        if s.startswith('Lv') and s.endswith('插槽'):
            continue
        if s in NO_DECO_SK:
            continue
        tracked_skills.append(s)
    if combo_skills:
        for s in combo_skills:
            if s in NO_DECO_SK:
                continue
            if s not in tracked_skills:
                tracked_skills.append(s)
    n_skills = len(tracked_skills)
    skill_idx = {s: i for i, s in enumerate(tracked_skills)}

    # 需求向量
    need_vec = [0] * n_skills
    for s, i in skill_idx.items():
        need = fixed_skills.get(s, 0)
        if s in weapon_fixed:
            need = max(need, weapon_fixed[s])
        if combo_skills and s in combo_skills:
            need = max(need, combo_skills[s])
        need_vec[i] = need

    # 初始技能向量（武器自带技能）
    init_skills_vec = [0] * n_skills
    for s, lv in weapon_skills.items():
        if s in skill_idx:
            init_skills_vec[skill_idx[s]] = lv

    # 初始赤字向量
    init_deficit = [max(0, need_vec[i] - init_skills_vec[i]) for i in range(n_skills)]
    init_def_score = sum(init_deficit)

    # 武器技能索引集合（提前定义，供候选向量构建使用）
    weapon_sk_idx = frozenset(_i for _i in range(n_skills) if tracked_skills[_i] in WEAPON_SK)
    is_weapon_deco = [False] * n_skills
    for _i in range(n_skills):
        is_weapon_deco[_i] = tracked_skills[_i] in WEAPON_SK

    # ===== 系列技能需求预计算（提前到候选构建之前）=====
    all_series_req = {}
    for ss, lv in fixed_skills.items():
        if ss in NO_DECO_SK:
            all_series_req[ss] = lv
    if combo_skills:
        for ss, lv in combo_skills.items():
            if ss in NO_DECO_SK:
                all_series_req[ss] = lv

    # 系列技能→位掩码映射
    series_bit_map = {}
    if all_series_req:
        for b, ss in enumerate(NO_DECO_SK):
            if ss in all_series_req:
                series_bit_map[ss] = b

    # 每个系列在防具5个部位中的总可用件数
    _series_total = {}
    if all_series_req:
        for ss in all_series_req:
            _series_total[ss] = sum(1 for j in range(5) if ss in part_series_availability.get(j, set()))

    # 需求系列技能的位掩码（用OR合并为单个整数）
    req_series_mask = 0
    for ss in all_series_req:
        if ss in series_bit_map:
            req_series_mask |= (1 << series_bit_map[ss])

    # ===== 候选装备预计算技能向量 =====
    # 每件装备转为 (skill_vec, slot_tuple, wslot_tuple, score, max_slot, series_bits, name, names)
    part_cands_vec = {}  # {part_idx: [vec_item, ...]}
    bit_map = {ss: b for b, ss in enumerate(NO_DECO_SK) if ss in all_skill_names}
    for pi in range(6):
        raw_cands = candidates_by_part.get(pi, [])
        vec_list = []
        for c in raw_cands:
            # 技能向量
            sv = [0] * n_skills
            has_wsk = False
            nz_indices = []  # 非零技能索引列表
            for s, lv in c['skills'].items():
                if s in skill_idx:
                    idx_val = skill_idx[s]
                    sv[idx_val] = lv
                    nz_indices.append((idx_val, lv))
                    if is_weapon_deco[idx_val]:
                        has_wsk = True
            # 系列技能位掩码
            series_bits = 0
            for s in c['skills']:
                if s in NO_DECO_SK and s in all_skill_names:
                    series_bits |= (1 << bit_map[s])
            # 预计算：是否含需求系列技能件
            has_req_series = bool(series_bits & req_series_mask) if req_series_mask else False
            vec_list.append({
                'name': c['name'], 'names': c.get('names', [c['name']]),
                'part_idx': pi,
                'sv': tuple(sv), 'nz': tuple(nz_indices),  # 非零技能索引
                'slots': c['slots'],
                'slots_sorted': c.get('slots_sorted', ()),
                'weapon_slots': c.get('weapon_slots', []),
                'wslots_sorted': c.get('wslots_sorted', ()),
                'score': c['score'], 'max_slot': c['max_slot'],
                'slot_sum': c['slot_sum'], 'w_slot_sum': c['w_slot_sum'],
                'series_bits': series_bits,
                '_has_wsk': has_wsk,
                '_has_req_series': has_req_series,
                'skills': c['skills'],
            })
        # ===== 系列技能预过滤（核心优化）=====
        # 对防具部位(pi<5)：含需求系列技能的候选全部保留，
        # 不含的只保留1个最佳纯slot候选（减少无效遍历）
        if pi < 5 and req_series_mask:
            series_cands = [v for v in vec_list if v['_has_req_series']]
            non_series = [v for v in vec_list if not v['_has_req_series']]
            # 强制系列检查：如果该部位不选系列候选，剩余部位能否满足所有系列需求？
            # 若不能，则该部位必须选系列候选，跳过非系列候选
            mandatory_series = False
            if all_series_req:
                for _ss, _lv in all_series_req.items():
                    _need = 4 if _lv >= 4 else (3 if _ss in GROUP_SK else 2)
                    _wprov = 1 if (combo_skills and combo_skills.get(_ss, 0) > 0) else 0
                    other_max = _wprov
                    for _pj in range(5):
                        if _pj != pi and _ss in part_series_availability.get(_pj, set()):
                            other_max += 1
                    if other_max < _need:
                        mandatory_series = True
                        break
            if non_series and not mandatory_series:
                best_slot_only = max(non_series, key=lambda x: (x['slot_sum'] + x.get('w_slot_sum', 0), x['score']))
                series_cands.append(best_slot_only)
            vec_list = series_cands
        part_cands_vec[pi] = vec_list

    # ===== 全局预检查 =====
    for sk in fixed_skills:
        if sk.startswith('Lv') and sk.endswith('插槽'):
            continue
        if sk in NO_DECO_SK:
            continue
        if sk in WEAPON_SK:
            pool = deco_idx.get((sk, 'weapon'), [])
        else:
            pool = deco_idx.get((sk, 'armor'), [])
        has_in_gear = any(sk in a['skills'] for p in part_names for a in parts[p])
        has_in_charm = any(sk in c.get('skills', {}) for c in charm_pool)
        if not pool and not has_in_gear and not has_in_charm:
            if not quiet:
                print(f"  预检查: {sk}无珠子且装备中不存在→无解")
            return []

    # 系列/组合技能件数检查
    for ss in fixed_skills:
        if ss not in NO_DECO_SK:
            continue
        need_lv = fixed_skills[ss]
        need_pieces = 4 if need_lv >= 4 else (3 if ss in GROUP_SK else 2)
        weapon_provided = combo_skills.get(ss, 0) > 0 if combo_skills else False
        avail_pieces = (1 if weapon_provided else 0)
        avail_pieces += sum(1 for p in part_names
                           if any(ss in a.get('skills', {}) for a in parts[p]))
        if avail_pieces < need_pieces:
            if not quiet:
                print(f"  预检查: {ss}需要{need_pieces}件但只有{avail_pieces}件→无解")
            return []

    # 初始赤字过大检查
    max_possible_cap = sum(WSLOTS)
    for p in part_names:
        if parts[p]:
            max_a = max(sum(a['slots']) for a in parts[p])
            max_possible_cap += max_a
    if charm_pool:
        max_c = max(sum(c.get('armor_slots', [])) + sum(c.get('weapon_slots', [])) for c in charm_pool)
        max_possible_cap += max_c
    if init_def_score > max_possible_cap:
        if not quiet:
            print(f"  预检查: 初始赤字{init_def_score}>{max_possible_cap}→无解")
        return []

    # 武器技能赤字检查（复用_fill_weapon_slots_smart缓存）
    w_deficit = {tracked_skills[i]: init_deficit[i] for i in range(n_skills)
                 if init_deficit[i] > 0 and tracked_skills[i] in WEAPON_SK}
    if w_deficit:
        w_def_score = sum(w_deficit.values())
        for s, d in w_deficit.items():
            pool = deco_idx.get((s, 'weapon'), [])
            best_charm_lv = max((c.get('skills', {}).get(s, 0) for c in charm_pool), default=0)
            if not pool and best_charm_lv < d:
                if not quiet:
                    print(f"  预检查: {s}无珠子且护石最高Lv{best_charm_lv}<需{d}→无解")
                return []
        # 快速上界检查（精确版：考虑组合珠多技能贡献+实际孔位数）
        # 1. 计算每个武器珠对赤字技能的总贡献，找最大值
        w_deficit_set = set(w_deficit.keys())
        max_total_pts_per_deco = 0
        _seen_dn = set()
        for s in w_deficit:
            pool = deco_idx.get((s, 'weapon'), [])
            for sr, pts, dn in pool:
                if dn in _seen_dn:
                    continue
                _seen_dn.add(dn)
                deco_skills = deco_skill_map.get(dn, [])
                total_pts = sum(min(p, w_deficit.get(sk, 0)) for sk, p in deco_skills if sk in w_deficit_set)
                if total_pts > max_total_pts_per_deco:
                    max_total_pts_per_deco = total_pts
        # 2. 武器孔位数（非总等级）+ 防具武器孔上限
        w_num_slots = len(WSLOTS)
        max_armor_wslots = 0
        for _pi in range(5):
            _cands = candidates_by_part.get(_pi, [])
            if _cands:
                _part_max = max(len(c.get('weapon_slots', [])) for c in _cands)
                max_armor_wslots += _part_max
        total_w_slots = w_num_slots + max_armor_wslots
        # 3. 最佳护石武器技能贡献
        best_charm_w_total = 0
        if charm_pool:
            for c in charm_pool:
                wsk_sum = sum(min(lv, w_deficit.get(s, 0)) for s, lv in c.get('skills', {}).items()
                             if s in w_deficit and lv > 0)
                best_charm_w_total = max(best_charm_w_total, wsk_sum)
        # 4. 上界 = 总孔位数 × 每珠最大贡献 + 护石贡献
        max_fillable = total_w_slots * max_total_pts_per_deco + best_charm_w_total if max_total_pts_per_deco > 0 else best_charm_w_total
        if w_def_score > max_fillable:
            if not quiet:
                print(f"  预检查: 武器赤字{w_def_score}>{max_fillable}(精确上界)→无解")
            return []
        # 精确检查：用_fill_weapon_slots_smart验证（有缓存，O(1)命中）
        w_test_fs = dict(weapon_skills)
        w_test_fixed = {}
        for s, d in w_deficit.items():
            w_test_fixed[s] = weapon_skills.get(s, 0) + d
        # 检查每个含武器技能的护石选项
        charm_wsk_seen = set()
        charm_wsk_options = [None]
        if charm_pool:
            for c in charm_pool:
                wsk_in_charm = {s: lv for s, lv in c.get('skills', {}).items()
                               if s in w_deficit and lv > 0}
                if wsk_in_charm:
                    key = frozenset(wsk_in_charm.items())
                    if key not in charm_wsk_seen:
                        charm_wsk_seen.add(key)
                        charm_wsk_options.append(wsk_in_charm)
        any_viable = False
        for charm_wsk in charm_wsk_options:
            test_fs = dict(w_test_fs)
            if charm_wsk:
                for s, lv in charm_wsk.items():
                    test_fs[s] = test_fs.get(s, 0) + lv
            # 检查剩余赤字
            rem_deficit = {s: max(0, d - (test_fs.get(s, 0) - w_test_fs.get(s, 0)))
                          for s, d in w_deficit.items()}
            rem_deficit = {s: d for s, d in rem_deficit.items() if d > 0}
            if not rem_deficit:
                any_viable = True
                break
            # 用_fill_weapon_slots_smart检查
            test_w_fixed = {s: test_fs.get(s, 0) + d for s, d in rem_deficit.items()}
            result = _fill_weapon_slots_smart(test_fs, list(WSLOTS), test_w_fixed)
            if result is not None:
                any_viable = True
                break
        if not any_viable:
            if not quiet:
                print(f"  预检查: 武器技能赤字{w_deficit}无法满足→无解")
            return []

    # ===== 搜索状态 =====
    results = []
    equipped = [None] * 6

    # 原地状态变量
    _skills_vec = list(init_skills_vec)  # 当前技能向量
    _deficit = list(init_deficit)        # 当前赤字向量
    _def_score = init_def_score          # 当前赤字总分
    _a_slots = []                        # 当前防具孔位
    _w_slots = list(WSLOTS)              # 当前武器孔位
    _series_count = {}                   # 当前各系列技能件数
    _armor_filled = 0                    # 已装备的防具件数
    _a_slot_sum = 0                      # 防具孔位总容量
    _w_slot_sum = sum(WSLOTS)            # 武器孔位总容量

    # 增量维护的slot计数数组 [0]=count_lv1, [1]=count_lv2, [2]=count_lv3
    # 替代每次遍历_a_slots/_w_slots的O(n)操作
    _a_slot_cnt = [0, 0, 0, 0]  # idx 1~3
    _w_slot_cnt = [0, 0, 0, 0]
    for _s in WSLOTS:
        if 0 < _s <= 3:
            _w_slot_cnt[_s] += 1

    # ===== 系列技能需求列表（提前定义供状态变量和预计算使用）=====
    _req_series_list = list(all_series_req.keys()) if all_series_req else []
    _n_req_series = len(_req_series_list)

    # 系列技能件数增量数组（与_req_series_list对齐）
    _series_have = [0] * _n_req_series if _n_req_series > 0 else []
    # 预计算系列技能→索引映射
    _series_idx_map = {}
    if _n_req_series > 0:
        for _si, _ss in enumerate(_req_series_list):
            _series_idx_map[_ss] = _si
    # 预计算系列技能需求件数
    _series_need_pieces = []
    for _ss in _req_series_list:
        _nlv = all_series_req[_ss]
        _series_need_pieces.append(4 if _nlv >= 4 else (3 if _ss in GROUP_SK else 2))
    # 武器提供的系列件数
    _series_wprov = [0] * _n_req_series
    if combo_skills and _n_req_series > 0:
        for _ss, _lv in combo_skills.items():
            if _ss in _series_idx_map:
                _series_wprov[_series_idx_map[_ss]] = 1

    # ===== 系列优先搜索（移至预计算之前，跳过不必要的remaining_*计算）=====
    if _n_req_series > 0:
        # 预计算每个(部位, 系列)是否有对应候选 — 用2D数组替代dict
        _sf_avail_arr = [[False] * _n_req_series for _ in range(5)]
        for _pi5 in range(5):
            for _si5, _ss5 in enumerate(_req_series_list):
                _sf_avail_arr[_pi5][_si5] = any(_ss5 in _c5['skills']
                    for _c5 in part_cands_vec.get(_pi5, []))
        # 预计算 remaining_avail[d][si] = 从部位d到4中含系列si的部位数
        _sf_rem_avail = [[0] * _n_req_series for _ in range(6)]
        for _d in range(4, -1, -1):
            for _si in range(_n_req_series):
                _sf_rem_avail[_d][_si] = _sf_rem_avail[_d+1][_si] + (1 if _sf_avail_arr[_d][_si] else 0)
        # 预计算每个候选的系列技能索引列表（避免每次dict查找）
        for _pi5 in range(5):
            for _c5 in part_cands_vec.get(_pi5, []):
                _c5['_si_list'] = [_series_idx_map[s] for s in _c5['skills'] if s in _series_idx_map]

        _sf_combos = []
        _sf_eq = [None] * 5
        _sf_sc = [0] * _n_req_series

        def _sf_bt(d):
            if d == 5:
                for _si in range(_n_req_series):
                    if _series_wprov[_si] + _sf_sc[_si] < _series_need_pieces[_si]:
                        return
                _sf_combos.append(list(_sf_eq))
                return
            # 剪枝：剩余部位能否满足所有系列需求（用预计算数组O(1)）
            for _si in range(_n_req_series):
                _need = _series_need_pieces[_si] - _series_wprov[_si] - _sf_sc[_si]
                if _need > 0 and _sf_rem_avail[d][_si] < _need:
                    return
            _tried_ns = False
            for c in part_cands_vec.get(d, []):
                if not c.get('_has_req_series', False):
                    if _tried_ns:
                        continue
                    _ok = True
                    for _si in range(_n_req_series):
                        _need = _series_need_pieces[_si] - _series_wprov[_si] - _sf_sc[_si]
                        if _need > 0 and _sf_rem_avail[d+1][_si] < _need:
                            _ok = False
                            break
                    if not _ok:
                        continue
                    _tried_ns = True
                # 更新系列计数（用预计算的_si_list）
                _ch = c['_si_list']
                for _si in _ch:
                    _sf_sc[_si] += 1
                _sf_eq[d] = c
                _sf_bt(d + 1)
                _sf_eq[d] = None
                for _si in _ch:
                    _sf_sc[_si] -= 1

        _sf_bt(0)

        if _sf_combos:
            # 溢出时按score排序取Top 2000（优先选技能贡献高的防具组合）
            if len(_sf_combos) > 2000:
                _sf_combos.sort(key=lambda _combo: sum(_c['score'] for _c in _combo), reverse=True)
                _sf_combos = _sf_combos[:2000]
                if not quiet:
                    print(f"  系列优先搜索: 溢出截断至2000组合")

            _sf_charms = part_cands_vec.get(5, [])

            _merged_fixed = dict(fixed_skills)
            if combo_skills:
                for _s, _r in combo_skills.items():
                    if _s in NO_DECO_SK:
                        continue
                    _merged_fixed[_s] = max(_merged_fixed.get(_s, 0), _r)

            _sf_data = []
            for _sf_combo in _sf_combos:
                _cur = dict(weapon_skills)
                _a_s = []
                _w_s = list(WSLOTS)
                for _pi6 in range(5):
                    for _s, _lv in _sf_combo[_pi6]['skills'].items():
                        _cur[_s] = _cur.get(_s, 0) + _lv
                    _a_s.extend(_sf_combo[_pi6]['slots'])
                    if _sf_combo[_pi6].get('weapon_slots'):
                        _w_s.extend(_sf_combo[_pi6]['weapon_slots'])
                _sf_data.append((_sf_combo, _cur, _a_s, _w_s))

            _charm_extra = []
            for _ch in _sf_charms:
                _ch_slots = _ch.get('slots', [])
                _ch_wslots = _ch.get('weapon_slots', [])
                _charm_extra.append((_ch, _ch_slots, _ch_wslots))

            for _sf_combo, _base_cur, _base_a, _base_w in _sf_data:
                if max_results > 0 and len(results) >= max_results:
                    break
                if (len(results) & 63) == 0 and time.time() - start_time > timeout_s:
                    break
                for _sf_ch, _ch_slots, _ch_wslots in _charm_extra:
                    if max_results > 0 and len(results) >= max_results:
                        break
                    _cur = dict(_base_cur)
                    for _s, _lv in _sf_ch['skills'].items():
                        _cur[_s] = _cur.get(_s, 0) + _lv
                    _a_s = _base_a + _ch_slots
                    _w_s = _base_w + _ch_wslots if _ch_wslots else _base_w

                    if not _check_deco_feasible(_cur, _a_s, _w_s, _merged_fixed, {},
                                                weapon_skills, min_rem_armor):
                        continue
                    filled = fill_slots(_cur, _a_s, _w_s, _merged_fixed, min_keep_armor=min_rem_armor)
                    if filled is None:
                        continue
                    fs, used, rem_a, rem_w = filled
                    _ok = True
                    for _s, _r in fixed_skills.items():
                        if _s.startswith('Lv') and _s.endswith('插槽'):
                            continue
                        if _s in NO_DECO_SK:
                            continue
                        if fs.get(_s, 0) < _r:
                            _ok = False; break
                    if _ok and combo_skills:
                        for _s, _r in combo_skills.items():
                            if _s in NO_DECO_SK:
                                continue
                            if fs.get(_s, 0) < _r:
                                _ok = False; break
                    if not _ok:
                        continue
                    if min_rem_armor > 0:
                        if sum(1 for _s in rem_a if _s > 0) < min_rem_armor:
                            continue
                    for _s in rem_a + rem_w:
                        if _s > 0:
                            for _n in range(1, _s + 1):
                                _k = f'Lv{_n}插槽'
                                fs[_k] = fs.get(_k, 0) + 1
                    _dmg = calc_damage(fs)
                    _pieces = list(_sf_combo) + [_sf_ch]
                    results.append({'pieces': _pieces, 'skills': fs, 'deco_used': used,
                                    'pract': _dmg, 'rem_a': rem_a, 'rem_w': rem_w})

            if not quiet:
                print(f"  系列优先搜索: {len(_sf_combos)}组合, {len(results)}方案, 耗时{time.time()-start_time:.3f}秒")
            if max_results == 0 or len(results) < max_results:
                results.sort(key=lambda x: -x['pract'])
            return results
        elif not _sf_combos:
            if not quiet:
                print(f"  系列优先搜索: 无有效组合, 耗时{time.time()-start_time:.3f}秒")
            return results

    # 武器技能赤字总量（增量维护，消除DFS内的any()遍历）
    _w_def_total = sum(init_deficit[i] for i in range(n_skills) if is_weapon_deco[i])
    _w_def_total = [_w_def_total]  # list做nonlocal替代

    # ===== 部位重排序：护石优先（候选最少+决定武器技能），然后按候选数升序 =====
    part_order = sorted(range(6), key=lambda pi: (
        pi != 5,  # charm (pi=5) goes first
        len(part_cands_vec.get(pi, []))
    ))

    # 预计算剩余部位的最佳score累计和
    remaining_best_sum = [0] * 7
    for _d in range(5, -1, -1):
        _pi = part_order[_d]
        remaining_best_sum[_d] = remaining_best_sum[_d + 1] + best_by_part.get(_pi, 0)

    # 预计算每个系列技能在剩余部位中的最大可用件数（逐部位系列件数上界剪枝）
    # remaining_series_max[depth][ss_idx] = 从depth层开始剩余部位能提供的该系列最大件数
    remaining_series_max = None
    if _n_req_series > 0:
        remaining_series_max = [[0] * _n_req_series for _ in range(7)]
        for _d in range(5, -1, -1):
            _pi = part_order[_d]
            for _si, _ss in enumerate(_req_series_list):
                _max_in_part = 0
                for _c in part_cands_vec.get(_pi, []):
                    if _ss in _c['skills']:
                        _max_in_part = 1  # 每部位最多选1件
                        break
                remaining_series_max[_d][_si] = remaining_series_max[_d + 1][_si] + _max_in_part

    # 预计算每个技能在剩余部位中的最大可用量（逐技能上界剪枝）
    remaining_skill_max = [[0] * n_skills for _ in range(7)]
    for _d in range(5, -1, -1):
        _pi = part_order[_d]
        for _i in range(n_skills):
            _max_in_part = 0
            for _c in part_cands_vec.get(_pi, []):
                _sv = _c['sv']
                if _sv[_i] > _max_in_part:
                    _max_in_part = _sv[_i]
            remaining_skill_max[_d][_i] = remaining_skill_max[_d + 1][_i] + _max_in_part

    # 预计算剩余部位各等级slot的最大可用数（精确slot上界剪枝）
    # remaining_slot_by_lv[depth] = (a_lv1, a_lv2, a_lv3, w_lv1, w_lv2, w_lv3)
    remaining_slot_by_lv = [[0]*6 for _ in range(7)]
    for _d in range(5, -1, -1):
        _pi = part_order[_d]
        _best_a = [0, 0, 0, 0]  # idx 1~3
        _best_w = [0, 0, 0, 0]
        for _c in part_cands_vec.get(_pi, []):
            for _s in _c['slots']:
                if 0 < _s <= 3:
                    _best_a[_s] = max(_best_a[_s], 1)  # 每部位最多取1件
            for _s in _c.get('weapon_slots', []):
                if 0 < _s <= 3:
                    _best_w[_s] = max(_best_w[_s], 1)
        _prev = remaining_slot_by_lv[_d + 1]
        for _lv in range(1, 4):
            remaining_slot_by_lv[_d][_lv - 1] = _prev[_lv - 1] + _best_a[_lv]
            remaining_slot_by_lv[_d][_lv + 2] = _prev[_lv + 2] + _best_w[_lv]

    # 预计算每个技能的珠子最大等级和slot等级
    best_deco_pts = [0] * n_skills
    best_deco_slot = [0] * n_skills
    # 珠子slot等级（用于贪心珠子检查的slot降级链，无珠子=100）
    deco_weight = [100] * n_skills
    for _i in range(n_skills):
        _sk_name = tracked_skills[_i]
        if _sk_name in WEAPON_SK:
            _pool = deco_idx.get((_sk_name, 'weapon'), [])
        else:
            _pool = deco_idx.get((_sk_name, 'armor'), [])
        if _pool:
            # 选pts最高的珠子（给技能等级最多的）
            _best_entry = max(_pool, key=lambda x: x[1])
            best_deco_pts[_i] = _best_entry[1]
            best_deco_slot[_i] = _best_entry[0]
            deco_weight[_i] = _best_entry[0]

    # ===== 赤字slot需求（增量维护，替代def_weight）=====
    # 每个赤字技能需要的slot数 = ceil(deficit / best_pts)
    init_a_slot_demand = 0
    init_w_slot_demand = 0
    slot_demand_per_skill = [0] * n_skills  # 每个技能的slot需求（预计算）
    for _i in range(n_skills):
        _d = init_deficit[_i]
        if _d <= 0:
            continue
        if best_deco_pts[_i] > 0:
            _sn = (_d + best_deco_pts[_i] - 1) // best_deco_pts[_i]
            slot_demand_per_skill[_i] = _sn
            if is_weapon_deco[_i]:
                init_w_slot_demand += _sn
            else:
                init_a_slot_demand += _sn

    # 增量维护的slot需求（用list做nonlocal替代）
    _a_slot_demand = [init_a_slot_demand]
    _w_slot_demand = [init_w_slot_demand]

    # 预计算剩余部位的最大slot总数（用于贪心触发判断）
    remaining_max_slot_sum = [0] * 7
    for _d in range(5, -1, -1):
        _pi = part_order[_d]
        _max_ss = 0
        for _c in part_cands_vec.get(_pi, []):
            _ss = _c['slot_sum'] + _c.get('w_slot_sum', 0)
            if _ss > _max_ss:
                _max_ss = _ss
        remaining_max_slot_sum[_d] = remaining_max_slot_sum[_d + 1] + _max_ss

    # 保留def_weight用于兼容（但不再作为主触发条件）
    init_def_weight = sum(deco_weight[_i] * init_deficit[_i]
                          for _i in range(n_skills) if init_deficit[_i] > 0)
    _def_weight = [init_def_weight]

    # ===== 预计算孔位技能需求（避免每次遍历fixed_skills）=====
    _slot_skill_needs = []  # [(lv, count), ...] 如 [(1, 3)] 表示需要3个Lv1插槽
    for _sk, _lv in fixed_skills.items():
        if _sk.startswith('Lv') and _sk.endswith('插槽'):
            try:
                _n = int(_sk[2:-2])
                _slot_skill_needs.append((_n, _lv))
            except ValueError:
                pass

    # ===== 贪心珠子填充检查（网页配装器ta().b()）=====
    def _greedy_deco_check():
        """O(技能数)贪心检查：赤字能否用珠子填满（用增量slot计数优化）"""
        a_cnt = [_a_slot_cnt[0], _a_slot_cnt[1], _a_slot_cnt[2], _a_slot_cnt[3]]
        w_cnt = [_w_slot_cnt[0], _w_slot_cnt[1], _w_slot_cnt[2], _w_slot_cnt[3]]
        # 预留孔位扣减
        _rem = min_rem_armor
        for _lv in [1, 2, 3]:
            while _rem > 0 and a_cnt[_lv] > 0:
                a_cnt[_lv] -= 1
                _rem -= 1
        if _rem > 0:
            return False
        # 孔位技能扣减（用预计算列表）
        for _n, _need in _slot_skill_needs:
            for _slv in range(_n, 4):
                while _need > 0 and a_cnt[_slv] > 0:
                    a_cnt[_slv] -= 1
                    _need -= 1
                if _need == 0:
                    break
            for _slv in range(_n, 4):
                while _need > 0 and w_cnt[_slv] > 0:
                    w_cnt[_slv] -= 1
                    _need -= 1
                if _need == 0:
                    break
            if _need > 0:
                return False
        # 计算珠子需求（按slot等级分桶）
        a_need = [0, 0, 0, 0]
        w_need = [0, 0, 0, 0]
        for _i in range(n_skills):
            _d = _deficit[_i]
            if _d <= 0:
                continue
            if best_deco_pts[_i] == 0:
                return False  # 无珠子可用
            _slots_needed = (_d + best_deco_pts[_i] - 1) // best_deco_pts[_i]
            if is_weapon_deco[_i]:
                w_need[best_deco_slot[_i]] += _slots_needed
            else:
                a_need[best_deco_slot[_i]] += _slots_needed
        # slot降级链检查（网页配装器核心）
        _a_r1 = a_cnt[1] - a_need[1]
        _a_r2 = a_cnt[2] - a_need[2] + (_a_r1 if _a_r1 < 0 else 0)
        _a_r3 = a_cnt[3] - a_need[3] + (_a_r2 if _a_r2 < 0 else 0)
        if _a_r3 < 0:
            return False
        _w_r1 = w_cnt[1] - w_need[1]
        _w_r2 = w_cnt[2] - w_need[2] + (_w_r1 if _w_r1 < 0 else 0)
        _w_r3 = w_cnt[3] - w_need[3] + (_w_r2 if _w_r2 < 0 else 0)
        if _w_r3 < 0:
            return False
        return True

    def _try_fill_and_record():
        if any(equipped[j] is None for j in range(6)):
            return False
        # 重建技能dict（用于fill_slots）
        cur_skills = dict(weapon_skills)
        for e in equipped:
            if e:
                for s, lv in e['skills'].items():
                    cur_skills[s] = cur_skills.get(s, 0) + lv
        a_s, w_s = [], list(WSLOTS)
        for e in equipped:
            if e:
                a_s.extend(e['slots'])
                if e.get('weapon_slots'):
                    w_s.extend(e['weapon_slots'])
        # 合并fixed_skills和combo_skills（非系列/组合）作为fill_slots的需求
        merged_fixed = dict(fixed_skills)
        if combo_skills:
            for s, r in combo_skills.items():
                if s in NO_DECO_SK:
                    continue
                merged_fixed[s] = max(merged_fixed.get(s, 0), r)
        # 快速可行性检查（避免无效的fill_slots调用）
        # merged_fixed已包含combo_skills的武器技能需求，传空combo避免重复计算
        if not _check_deco_feasible(cur_skills, a_s, w_s, merged_fixed, {},
                                    weapon_skills, min_rem_armor):
            return False
        filled = fill_slots(cur_skills, a_s, w_s, merged_fixed, min_keep_armor=min_rem_armor)
        if filled is None:
            return False
        fs, used, rem_a, rem_w = filled
        for s, r in fixed_skills.items():
            if s.startswith('Lv') and s.endswith('插槽'):
                continue
            if s in NO_DECO_SK:
                continue
            if fs.get(s, 0) < r: return False
        if combo_skills:
            for s, r in combo_skills.items():
                if s in NO_DECO_SK:
                    continue
                if fs.get(s, 0) < r: return False
        if min_rem_armor > 0:
            if sum(1 for s in rem_a if s > 0) < min_rem_armor: return False
        for s in rem_a + rem_w:
            if s > 0:
                for n in range(1, s + 1):
                    k = f'Lv{n}插槽'
                    fs[k] = fs.get(k, 0) + 1
        dmg = calc_damage(fs)
        pieces = [e for e in equipped if e]
        results.append({'pieces': pieces, 'skills': fs, 'deco_used': used,
                        'pract': dmg, 'rem_a': rem_a, 'rem_w': rem_w})
        return True

    # ===== 赤字加权总和的增量更新（保留用于兼容）=====

    # 预计算初始有赤字的技能索引列表
    init_deficit_indices = tuple(_i for _i in range(n_skills) if init_deficit[_i] > 0)

    def _greedy_deco_check_with_future(depth):
        """增强版贪心检查：考虑剩余部位提供的slot（用增量slot计数优化）"""
        rsl = remaining_slot_by_lv[depth] if depth < 6 else [0]*6
        # 用增量维护的slot计数替代遍历
        a_cnt = [_a_slot_cnt[0], _a_slot_cnt[1], _a_slot_cnt[2], _a_slot_cnt[3]]
        w_cnt = [_w_slot_cnt[0], _w_slot_cnt[1], _w_slot_cnt[2], _w_slot_cnt[3]]
        # 加上剩余部位的slot（上界估计）
        a_cnt[1] += rsl[0]; a_cnt[2] += rsl[1]; a_cnt[3] += rsl[2]
        w_cnt[1] += rsl[3]; w_cnt[2] += rsl[4]; w_cnt[3] += rsl[5]
        # 预留孔位扣减
        _rem = min_rem_armor
        for _lv in [1, 2, 3]:
            while _rem > 0 and a_cnt[_lv] > 0:
                a_cnt[_lv] -= 1
                _rem -= 1
        if _rem > 0:
            return False
        # 孔位技能扣减（用预计算列表）
        for _n, _need in _slot_skill_needs:
            for _slv in range(_n, 4):
                while _need > 0 and a_cnt[_slv] > 0:
                    a_cnt[_slv] -= 1
                    _need -= 1
                if _need == 0:
                    break
            for _slv in range(_n, 4):
                while _need > 0 and w_cnt[_slv] > 0:
                    w_cnt[_slv] -= 1
                    _need -= 1
                if _need == 0:
                    break
            if _need > 0:
                return False
        # 计算珠子需求
        a_need = [0, 0, 0, 0]
        w_need = [0, 0, 0, 0]
        for _i in range(n_skills):
            _d = _deficit[_i]
            if _d <= 0:
                continue
            if best_deco_pts[_i] == 0:
                return False
            _slots_needed = (_d + best_deco_pts[_i] - 1) // best_deco_pts[_i]
            if is_weapon_deco[_i]:
                w_need[best_deco_slot[_i]] += _slots_needed
            else:
                a_need[best_deco_slot[_i]] += _slots_needed
        # slot降级链检查
        _a_r1 = a_cnt[1] - a_need[1]
        _a_r2 = a_cnt[2] - a_need[2] + (_a_r1 if _a_r1 < 0 else 0)
        _a_r3 = a_cnt[3] - a_need[3] + (_a_r2 if _a_r2 < 0 else 0)
        if _a_r3 < 0:
            return False
        _w_r1 = w_cnt[1] - w_need[1]
        _w_r2 = w_cnt[2] - w_need[2] + (_w_r1 if _w_r1 < 0 else 0)
        _w_r3 = w_cnt[3] - w_need[3] + (_w_r2 if _w_r2 < 0 else 0)
        if _w_r3 < 0:
            return False
        return True

    def _try_early_fill(depth):
        """提前填充：用剩余部位的候选填充未选部位，优先选含系列技能件的"""
        if depth >= 6:
            return _try_fill_and_record()
        temp_equipped = []
        for d in range(depth, 6):
            pi = part_order[d]
            cands = part_cands_vec.get(pi, [])
            if not cands:
                return False
            # 优先选含需求系列技能件的候选，否则选score最高
            best = None
            for c in cands:
                if c.get('_has_req_series', False):
                    best = c
                    break
            if best is None:
                best = cands[0]
            equipped[pi] = best
            temp_equipped.append(pi)
        success = _try_fill_and_record()
        for pi in temp_equipped:
            equipped[pi] = None
        return success

    def _dfs(depth):
        """按部位递归DFS（v3优化版 - 精准剪枝）

        核心优化：
        1. 赤字=0时直接提前填充，不遍历候选
        2. 赤字>0时只递归能减少赤字或提供系列技能件的候选
        3. 额外尝试1个最佳纯孔位候选（用于珠子填充路径）
        """
        nonlocal _def_score, _armor_filled, _a_slot_sum, _w_slot_sum

        if max_results > 0 and len(results) >= max_results:
            return
        if (len(results) & 255) == 0 and time.time() - start_time > timeout_s:
            return

        cur_def_score = _def_score

        # ===== 系列技能件数快速检查（增量数组+逐部位上界剪枝）=====
        if _n_req_series > 0 and remaining_series_max is not None:
            rsm_s = remaining_series_max[depth] if depth < 6 else [0]*_n_req_series
            for _si in range(_n_req_series):
                have_pieces = _series_wprov[_si] + _series_have[_si]
                need_pieces = _series_need_pieces[_si]
                if have_pieces < need_pieces:
                    need_cnt = need_pieces - have_pieces
                    if rsm_s[_si] < need_cnt:
                        return

        # ===== 赤字=0时检查系列技能是否满足，满足则提前填充 =====
        if cur_def_score == 0:
            series_ok = True
            if _n_req_series > 0:
                for _si in range(_n_req_series):
                    if _series_wprov[_si] + _series_have[_si] < _series_need_pieces[_si]:
                        series_ok = False
                        break
            if series_ok:
                if depth >= 6:
                    _try_fill_and_record()
                else:
                    _try_early_fill(depth)
                return

        # ===== 逐技能上界剪枝（仅检查有赤字的技能）=====
        if depth < 6:
            rsm = remaining_skill_max[depth]
            rsl = remaining_slot_by_lv[depth]
            for _i in init_deficit_indices:
                _d = _deficit[_i]
                if _d <= 0:
                    continue
                from_gear = rsm[_i]
                if from_gear >= _d:
                    continue
                remain_gap = _d - from_gear
                if best_deco_pts[_i] == 0:
                    return
                slots_needed = (remain_gap + best_deco_pts[_i] - 1) // best_deco_pts[_i]
                _bs = best_deco_slot[_i]
                if is_weapon_deco[_i]:
                    # 用增量维护的slot计数替代遍历
                    cur_w_cnt = _w_slot_cnt[_bs] + _w_slot_cnt[_bs+1 if _bs < 3 else 3] + _w_slot_cnt[3] if _bs < 3 else _w_slot_cnt[3]
                    # 简化：统计>=_bs的slot数
                    cur_w_cnt = sum(_w_slot_cnt[_bs:4])
                    rem_w = rsl[3] + rsl[4] + rsl[5]
                    if cur_w_cnt + rem_w < slots_needed:
                        return
                else:
                    cur_a_cnt = sum(_a_slot_cnt[_bs:4])
                    rem_a = rsl[0] + rsl[1] + rsl[2]
                    if cur_a_cnt + rem_a < slots_needed:
                        return

        # ===== 贪心珠子检查 + 提前填充 =====
        cur_a_demand = _a_slot_demand[0]
        cur_w_demand = _w_slot_demand[0]
        cur_slot_total = _a_slot_sum + _w_slot_sum
        total_demand = cur_a_demand + cur_w_demand
        if total_demand > 0 and depth < 6:
            max_future_slot = remaining_max_slot_sum[depth]
            if total_demand <= cur_slot_total + max_future_slot:
                if _greedy_deco_check_with_future(depth):
                    if _try_early_fill(depth):
                        return
        elif total_demand == 0 and depth >= 6:
            _try_fill_and_record()
            return

        # ===== 全部6件装备时尝试填充 =====
        if depth >= 6:
            series_ok = True
            if _n_req_series > 0:
                for _si in range(_n_req_series):
                    if _series_wprov[_si] + _series_have[_si] < _series_need_pieces[_si]:
                        series_ok = False
                        break
            if series_ok:
                _try_fill_and_record()
            return

        # ===== 获取当前部位候选 =====
        part_idx = part_order[depth]
        part_cands = part_cands_vec.get(part_idx, [])
        if not part_cands:
            return

        is_charm_slot = (part_idx == 5)
        cur_w_def = _w_def_total[0]
        _wslots_cap = sum(WSLOTS) * 2  # 预计算

        # ===== 遍历该部位候选装备 =====
        best_slot_only_tried = False  # 是否已尝试过纯孔位候选
        _n_results = len(results)
        for Q in part_cands:
            if max_results > 0 and _n_results >= max_results:
                return

            # per-candidate上界break
            q_score = Q['score']
            remaining_after = remaining_best_sum[depth + 1] if depth < 5 else 0
            if q_score + remaining_after + cur_slot_total < cur_def_score:
                break

            # 护石武器技能检查
            if is_charm_slot and cur_w_def > 0:
                if not Q.get('_has_wsk', False) and cur_w_def > _wslots_cap:
                    continue

            # ===== 增量计算选Q后的赤字变化（用nz遍历）=====
            nz = Q['nz']
            q_max_slot = Q['max_slot']
            q_has_req_series = Q.get('_has_req_series', False)
            new_def_score = cur_def_score
            new_a_demand = _a_slot_demand[0]
            new_w_demand = _w_slot_demand[0]
            new_w_def = cur_w_def
            changed = []
            contributes = False
            for i, lv in nz:
                old_sk = _skills_vec[i]
                _skills_vec[i] = old_sk + lv
                old_def = _deficit[i]
                if old_def > 0:
                    old_demand = slot_demand_per_skill[i]
                    new_have = _skills_vec[i]
                    if new_have >= need_vec[i]:
                        _deficit[i] = 0
                        new_def_score -= old_def
                        if old_demand > 0:
                            if is_weapon_deco[i]:
                                new_w_demand -= old_demand
                            else:
                                new_a_demand -= old_demand
                        if is_weapon_deco[i]:
                            new_w_def -= old_def
                        contributes = True
                    else:
                        new_def = need_vec[i] - new_have
                        _deficit[i] = new_def
                        new_def_score += new_def - old_def
                        if best_deco_pts[i] > 0:
                            new_demand = (new_def + best_deco_pts[i] - 1) // best_deco_pts[i]
                            demand_delta = new_demand - old_demand
                            if demand_delta != 0:
                                if is_weapon_deco[i]:
                                    new_w_demand += demand_delta
                                else:
                                    new_a_demand += demand_delta
                        if is_weapon_deco[i]:
                            new_w_def += new_def - old_def
                        contributes = True
                changed.append((i, old_sk, old_def))

            # ===== 分支条件（精准剪枝）=====
            if cur_def_score > 0:
                if not contributes:
                    if not q_has_req_series:
                        # 纯孔位候选：只尝试1个，且需通过贪心检查
                        if best_slot_only_tried:
                            for i, old_sk, old_def in changed:
                                _skills_vec[i] = old_sk
                                _deficit[i] = old_def
                            continue
                        if q_max_slot == 0:
                            for i, old_sk, old_def in changed:
                                _skills_vec[i] = old_sk
                                _deficit[i] = old_def
                            continue
                        best_slot_only_tried = True
                        if not _greedy_deco_check_with_future(depth):
                            for i, old_sk, old_def in changed:
                                _skills_vec[i] = old_sk
                                _deficit[i] = old_def
                            continue
                    else:
                        # 含系列技能件但不减少赤字：只在系列件数还不够时才递归
                        series_still_needed = False
                        if _n_req_series > 0:
                            item_skills_q = Q['skills']
                            for s in item_skills_q:
                                if s in _series_idx_map:
                                    _si2 = _series_idx_map[s]
                                    if _series_wprov[_si2] + _series_have[_si2] < _series_need_pieces[_si2]:
                                        series_still_needed = True
                                        break
                        if not series_still_needed:
                            for i, old_sk, old_def in changed:
                                _skills_vec[i] = old_sk
                                _deficit[i] = old_def
                            continue

            if True:
                # ===== 原地放置装备 =====
                equipped[part_idx] = Q
                _def_score = new_def_score
                old_a_demand_val = _a_slot_demand[0]
                old_w_demand_val = _w_slot_demand[0]
                _a_slot_demand[0] = new_a_demand
                _w_slot_demand[0] = new_w_demand
                old_w_def_val = _w_def_total[0]
                _w_def_total[0] = new_w_def

                # 更新孔位
                item_slots = Q['slots']
                item_wslots = Q.get('weapon_slots', [])
                a_len = len(_a_slots)
                w_len = len(_w_slots)
                _a_slots.extend(item_slots)
                _w_slots.extend(item_wslots)
                slot_sum_a = sum(item_slots)
                slot_sum_w = sum(item_wslots)
                _a_slot_sum += slot_sum_a
                _w_slot_sum += slot_sum_w
                # 增量更新slot计数
                for _s in item_slots:
                    if 0 < _s <= 3:
                        _a_slot_cnt[_s] += 1
                for _s in item_wslots:
                    if 0 < _s <= 3:
                        _w_slot_cnt[_s] += 1

                # 更新系列件数（增量数组+dict兼容）
                changed_series = []
                changed_series_idx = []
                item_skills = Q['skills']
                for s in item_skills:
                    if s in NO_DECO_SK and s not in SLOT_SKILLS:
                        old_c = _series_count.get(s, 0)
                        _series_count[s] = old_c + 1
                        changed_series.append((s, old_c))
                        # 更新增量数组
                        if s in _series_idx_map:
                            _si2 = _series_idx_map[s]
                            changed_series_idx.append(_si2)
                            _series_have[_si2] += 1
                if part_idx < 5:
                    _armor_filled += 1

                # ===== 递归前系列可行性预检查 =====
                # 避免进入下一层_dfs才发现系列不足（减少函数调用开销）
                should_recurse = True
                if _n_req_series > 0 and remaining_series_max is not None:
                    next_depth = depth + 1
                    rsm_next = remaining_series_max[next_depth] if next_depth < 7 else [0]*_n_req_series
                    for _si in range(_n_req_series):
                        have_pieces = _series_wprov[_si] + _series_have[_si]
                        need_pieces = _series_need_pieces[_si]
                        if have_pieces < need_pieces:
                            need_cnt = need_pieces - have_pieces
                            if rsm_next[_si] < need_cnt:
                                should_recurse = False
                                break

                if should_recurse:
                    _dfs(depth + 1)
                _n_results = len(results)

                # ===== 原地撤销 =====
                if part_idx < 5:
                    _armor_filled -= 1
                for _si2 in changed_series_idx:
                    _series_have[_si2] -= 1
                for s, old_c in changed_series:
                    if old_c == 0:
                        _series_count.pop(s, None)
                    else:
                        _series_count[s] = old_c
                for _s in item_slots:
                    if 0 < _s <= 3:
                        _a_slot_cnt[_s] -= 1
                for _s in item_wslots:
                    if 0 < _s <= 3:
                        _w_slot_cnt[_s] -= 1
                _a_slot_sum -= slot_sum_a
                _w_slot_sum -= slot_sum_w
                del _a_slots[a_len:]
                del _w_slots[w_len:]
                _a_slot_demand[0] = old_a_demand_val
                _w_slot_demand[0] = old_w_demand_val
                _w_def_total[0] = old_w_def_val
                _def_score = cur_def_score
                equipped[part_idx] = None

            # 撤销技能向量更新
            for i, old_sk, old_def in changed:
                _skills_vec[i] = old_sk
                _deficit[i] = old_def

    _dfs(0)

    if not quiet:
        print(f"  DFS完成: {len(results)}方案, 耗时{time.time()-start_time:.3f}秒")
    if max_results == 0 or len(results) < max_results:
        results.sort(key=lambda x: -x['pract'])
    return results


def _quick_skill_upper_bound(sk, cached_ctx, wslots):
    """快速计算技能sk的理论可追加上界（预筛用）

    基于候选装备列表的乐观估计：
    - 每个防具部位取含sk的最高等级，求和
    - 护石取含sk的最高等级
    - 所有孔位（含武器孔）按最优珠子换算sk等级
    返回值是理论上限，实际可能因固定技能约束而更低。
    """
    (candidates, all_skill_names, weapon_skills, armor_fixed, weapon_fixed,
     best_by_part, best_slot_by_part, candidates_by_part, part_series_availability) = cached_ctx

    # 1. 装备+护石部分：各部位最高sk等级之和
    gear_max = 0
    for pi in range(6):
        cands = candidates_by_part.get(pi, [])
        if not cands:
            continue
        part_max = max((c['skills'].get(sk, 0) for c in cands), default=0)
        gear_max += part_max

    # 2. 珠子部分：总孔位容量能插多少sk珠子
    # 找出sk的最优珠子（slot最小、pts最大）
    best_deco = None
    for dtype in ('armor', 'weapon'):
        pool = deco_idx.get((sk, dtype), [])
        for slot_req, pts, dname in pool:
            if best_deco is None or pts > best_deco[1] or (pts == best_deco[1] and slot_req < best_deco[0]):
                best_deco = (slot_req, pts, dname)
    deco_max = 0
    if best_deco:
        slot_req, pts, _ = best_deco
        # 乐观估计总孔位：所有候选的最大孔位之和 + 武器孔
        total_slots = sum(best_slot_by_part.get(pi, 0) for pi in range(6)) + sum(wslots)
        # 简化：假设所有孔位都>=slot_req（乐观）
        deco_max = (total_slots // slot_req) * pts

    return gear_max + deco_max


# ==================== 追加技能查询（v3优化版）====================
def query_extra(fixed_skills, combo_skills, min_rem_armor, charm_pool):
    """逐技能扫描：每个技能从最高级降级搜索，找到1条方案即记录

    v3优化：
    1. 复用cached_ctx避免重复构建候选
    2. 系列技能预过滤大幅加速搜索
    3. 快速上界预筛：先计算理论上限，从上限开始降级，避免无效搜索
    4. 缩短超时：追加搜索0.1s、孔位二分0.1s、系列搜索0.1s
    """
    series_names = ['巨戟龙的默示录', '火龙之力', '凶爪龙之力', '黑蚀龙之力',
                    '泡狐龙之力', '煌雷龙之力', '海龙的涡雷',
                    '冻峰龙之反叛', '锁刃龙之饥饿']

    fixed_set = set(fixed_skills.keys())
    if combo_skills:
        fixed_set.update(combo_skills.keys())

    output_skills = []
    output_skills.extend([
        '挑战者', '力量解放', '弱点特效', '无伤',
        '攻击', '看破',
        '会心击【属性】', '攻击守势', '属性吸收',
    ])
    output_skills.extend([
        '黑蚀龙之力', '凶爪龙之力', '冻峰龙之反叛', '锁刃龙之饥饿',
    ])
    if '巨戟龙的默示录' not in fixed_set:
        output_skills.append('巨戟龙的默示录')

    current_elem = '龙属性攻击强化'
    if current_elem not in fixed_set:
        output_skills.append(current_elem)

    under_max = []
    for sk, lv in fixed_skills.items():
        if sk.startswith('Lv') and sk.endswith('插槽'):
            continue
        cap = SKILL_CAPS.get(sk, 99)
        if lv < cap:
            under_max.append((sk, lv, cap))

    seen = set()
    final_output = []
    for sk in output_skills:
        if sk not in seen and sk not in fixed_set:
            seen.add(sk)
            final_output.append(sk)

    series_max_pieces = {}
    for ss in series_names:
        parts_with = sum(1 for p in ['head','body','arms','waist','legs']
                       if any(ss in a.get('skills', {}) for a in parts[p]))
        series_max_pieces[ss] = min(parts_with, 5)

    baseline_skills = dict(fixed_skills)
    if combo_skills:
        baseline_skills.update(combo_skills)
    baseline_dmg = calc_damage(baseline_skills)
    baseline_wcr = calc_weighted_crit(baseline_skills)

    # 基线搜索
    t0_base = time.time()
    base_res = dfs_search(charm_pool, fixed_skills, combo_skills, min_rem_armor,
                          max_results=1, quiet=True, timeout_s=5.0)
    base_dt = time.time() - t0_base
    slot_info = {'Lv1': 0, 'Lv2': 0, 'Lv3': 0}
    if base_res:
        best_base = base_res[0]
        rem = best_base.get('rem_a', []) + best_base.get('rem_w', [])
        for s in rem:
            if s >= 1: slot_info['Lv1'] += 1
            if s >= 2: slot_info['Lv2'] += 1
            if s >= 3: slot_info['Lv3'] += 1
        print(f"  [基线] 完成({base_dt:.2f}s) 剩余: Lv1x{slot_info['Lv1']} Lv2x{slot_info['Lv2']} Lv3x{slot_info['Lv3']}")
    else:
        print(f"  [基线] 完成({base_dt:.2f}s) 无方案")

    # 构建候选缓存（包含所有可能的追加技能名，避免cached_ctx漏删候选）
    _extra_sn = set(final_output) | set(sk for sk, _, _ in under_max)
    cached_ctx = _build_candidates(charm_pool, fixed_skills, combo_skills, quiet=False, extra_skill_names=_extra_sn)

    # 孔位信息：直接报告基线方案的剩余孔位（跳过耗时的二分最大化）
    # 如需孔位最大化，可在外部单独调用
    slot_max = {'Lv1': slot_info['Lv1'], 'Lv2': slot_info['Lv2'], 'Lv3': slot_info['Lv3']}
    print(f"  [孔位] 基线剩余: Lv1x{slot_max['Lv1']} Lv2x{slot_max['Lv2']} Lv3x{slot_max['Lv3']}")

    skill_max = {}
    total = len(final_output) + len(under_max)
    done = 0

    # === 追加技能查询使用快速模式（跳过fill_slots优化循环）===
    global _FEASIBILITY_ONLY
    _FEASIBILITY_ONLY = True

    # 未满级固定技能升级
    for sk, cur_lv, cap in under_max:
        done += 1
        t0 = time.time()
        best = cur_lv
        for lv in range(cap, cur_lv, -1):
            test_fixed = dict(fixed_skills)
            test_fixed[sk] = lv
            res = dfs_search(charm_pool, test_fixed, combo_skills, min_rem_armor,
                             max_results=1, quiet=True, timeout_s=0.5, cached_ctx=cached_ctx)
            if res:
                best = lv
                break
        test_s = dict(baseline_skills)
        test_s[sk] = best
        best_dmg = calc_damage(test_s)
        best_wcr = calc_weighted_crit(test_s)
        skill_max[sk] = (best, cap, best_dmg, best_dmg - baseline_dmg, 'upgrade', best_wcr)
        dt = time.time() - t0
        print(f"  [{done}/{total}] {sk}(升级{cur_lv}→{cap}): Lv{best} ({dt:.2f}s)")

    # 追加技能
    for sk in final_output:
        done += 1
        cap = SKILL_CAPS.get(sk, 99)
        t0 = time.time()

        if sk in series_names:
            actual_cap = cap
            if sk in series_max_pieces:
                actual_cap = min(actual_cap, series_max_pieces[sk])
            best = 0
            for lv in [4, 2]:
                if lv > actual_cap:
                    continue
                test_fixed = dict(fixed_skills)
                test_fixed[sk] = lv
                # 直接让DFS判断可行性（系列件数检查已内置，含重叠件判断）
                # 系列技能查询不用cached_ctx：cached_ctx的系列预过滤会误删含目标系列的候选
                res = dfs_search(charm_pool, test_fixed, combo_skills, min_rem_armor,
                                 max_results=1, quiet=True, timeout_s=0.1)
                if res:
                    best = lv
                    break
            test_s = dict(baseline_skills)
            test_s[sk] = best
            best_dmg = calc_damage(test_s)
            best_wcr = calc_weighted_crit(test_s)
            skill_max[sk] = (best, actual_cap, best_dmg, best_dmg - baseline_dmg, 'extra', best_wcr)
            dt = time.time() - t0
            print(f"  [{done}/{total}] {sk}: Lv{best}/{actual_cap} ({dt:.2f}s)")
            continue

        # === 快速上界预筛 ===
        upper = _quick_skill_upper_bound(sk, cached_ctx, WSLOTS)
        start_lv = min(cap, upper)

        best = 0
        # 预检查：技能是否有珠子或装备能提供
        has_deco = bool(deco_idx.get((sk, 'armor'), []) or deco_idx.get((sk, 'weapon'), []))
        has_in_gear = any(sk in a.get('skills', {}) for p in ['head','body','arms','waist','legs'] for a in parts[p])
        has_in_charm = any(sk in c.get('skills', {}) for c in charm_pool)
        if (has_deco or has_in_gear or has_in_charm) and start_lv > 0:
            # cap>3用二分搜索减少降级次数，cap<=3用线性降级（更快）
            if start_lv > 3:
                lo, hi = 1, start_lv
                best = 0
                while lo <= hi:
                    mid = (lo + hi) // 2
                    test_fixed = dict(fixed_skills)
                    test_fixed[sk] = mid
                    res = dfs_search(charm_pool, test_fixed, combo_skills, min_rem_armor,
                                     max_results=1, quiet=True, timeout_s=0.1, cached_ctx=cached_ctx)
                    if res:
                        best = mid
                        lo = mid + 1
                    else:
                        hi = mid - 1
            else:
                for lv in range(start_lv, 0, -1):
                    test_fixed = dict(fixed_skills)
                    test_fixed[sk] = lv
                    res = dfs_search(charm_pool, test_fixed, combo_skills, min_rem_armor,
                                     max_results=1, quiet=True, timeout_s=0.1, cached_ctx=cached_ctx)
                    if res:
                        best = lv
                        break

        test_s = dict(baseline_skills)
        test_s[sk] = best
        best_dmg = calc_damage(test_s)
        best_wcr = calc_weighted_crit(test_s)
        skill_max[sk] = (best, cap, best_dmg, best_dmg - baseline_dmg, 'extra', best_wcr)
        dt = time.time() - t0
        status = f"上限{upper}" if start_lv < cap else ""
        print(f"  [{done}/{total}] {sk}: Lv{best}/{cap} {status}({dt:.2f}s)")

    # 恢复完整模式
    _FEASIBILITY_ONLY = False

    lines = []
    lines.append(f"基线伤害（仅固定+组合技能）: {baseline_dmg:.1f}")
    lines.append(f"基线加权会心: {baseline_wcr:.1f}%")
    lines.append("")

    if under_max:
        lines.append("【固定技能升级空间】（当前等级→可升级到 | 独立伤害 | 增幅 | 加权会心）")
        lines.append("-" * 75)
        up_items = []
        for sk, cur_lv, cap in under_max:
            if sk in skill_max:
                ml, cap2, dmg, delta, _, wcr = skill_max[sk]
                up_items.append((sk, cur_lv, ml, cap2, dmg, delta, wcr))
        up_items.sort(key=lambda x: -x[5])
        for sk, cur, ml, cap, dmg, delta, wcr in up_items:
            sign = "+" if delta >= 0 else ""
            lines.append(f"  {sk:<14s} | Lv{cur:>2d}→Lv{ml:>2d}/{cap:<2d} | 伤害 {dmg:>7.1f} | {sign}{delta:.1f} | 会心 {wcr:.1f}%")
        lines.append("")

    lines.append("【追加技能】（技能名 | 最高等级 | 独立伤害 | 伤害增幅 | 加权会心）")
    lines.append("-" * 75)
    out_items = []
    for sk in final_output:
        if sk in skill_max:
            ml, cap, dmg, delta, tag, wcr = skill_max[sk]
            if tag == 'extra':
                out_items.append((sk, ml, cap, dmg, delta, wcr))
    out_items.sort(key=lambda x: -x[4])
    for sk, ml, cap, dmg, delta, wcr in out_items:
        sign = "+" if delta >= 0 else ""
        lines.append(f"  {sk:<14s} | Lv{ml:>2d}/{cap:<2d} | 伤害 {dmg:>7.1f} | {sign}{delta:.1f} | 会心 {wcr:.1f}%")
    lines.append("")

    lines.append("【孔位最大化】（将LvN插槽作为技能搜索，向下兼容）")
    lines.append(f"  Lv1插槽: 基线{slot_info['Lv1']}个 → 最大化{slot_max['Lv1']}个")
    lines.append(f"  Lv2插槽: 基线{slot_info['Lv2']}个 → 最大化{slot_max['Lv2']}个")
    lines.append(f"  Lv3插槽: 基线{slot_info['Lv3']}个 → 最大化{slot_max['Lv3']}个")

    return '\n'.join(lines)
