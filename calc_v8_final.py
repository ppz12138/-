#!/usr/bin/env python3
"""
v8最终修复版 - 按用户反馈修正

武器系统理解(已确认):
  武器洗练: 1个系列技能(Lv1) + 1个组合技能(Lv1)
  - 组合技能是纯随机的，如果没洗出理想组合，武器中只有系列技能可用

  防具技能: 每件防具附带1个系列技能 + 1个组合技能
  - 巨戟龙防具特殊: 每件带2个系列技能(巨戟龙的默示录 + 另一个系列)
  
  系列技能件数: 无珠子/护石，只能通过装备凑
  - 普通系列技能: Lv2需2件(武器1+防具1), Lv4需4件(武器1+防具3)
  - 组合技能(GROUP_SK): Lv3需3件(武器1+防具2)
  
  组合技能来源: 武器和防具，不包括珠子和护石
  
  匹配算法: 系列/组合技能匹配算法跟其他技能一样
  - 武器自带技能直接计入总技能值，不需要从装备重复凑

PERM_ATK: 护符+6 + 猫饭+5 = 11 (技能加区，不计入面板)

黑蚀覆盖率:
  黑蚀≥2 + 无我之境3 → 60%覆盖
  黑蚀≥2 无无我之境 → 50%覆盖
"""
import time, itertools
from collections import Counter
import fast_search_v3 as fs

STATE_CN = {
    'rage':'愤怒','rengeki':'连击','mukizu':'无伤','weak':'弱点','furue':'精神抖擞',
    'oguard':'攻守','counter':'逆袭','rikikai':'力量解放',
    'kuroshoku':'黑蚀','kuroshoku_migo':'黑蚀+无我','none':'无'
}

BASE_FIXED_MIN = {
    '耳塞': 2, '利刃': 3, '缓冲': 1, '快吃': 3, 'Lv1插槽': 3,
}

# 伤害相关核心技能(用于展示)
DAMAGE_SKILLS = [
    '格挡性能','广域化','精神抖擞','攻击','攻击守势','超会心','会心击【属性】',
    '弱点特效','看破','逆袭','无伤','无我之境','挑战者','连击',
    '巨戟龙的默示录','龙属性攻击强化','霸主之魂','火龙之力','黑蚀龙之力',
]


def make_core_for_plan(weapon_sk, is_wide=False, extra_fixed=None):
    """按武器技能生成可行的核心配置列表
    
    core配置 = 必须通过装备凑齐的技能(不含武器自带)
    搜索时会优先选择满足core的装备，然后用珠子/护石补全剩余技能
    伤害优先级由fast_search_v3._deco_priority_score自动处理
    
    设计原则:
    - 系列/组合技能必须在core中(只能由防具提供)
    - 武器技能(攻击守势等)需要在core中或由武器孔填充
    - 其他伤害技能(攻击/超心/看破/无我等)由算法自动补全
    - 如果extra_fixed已包含系列技能，则core不再重复要求
    """
    has = lambda s: s in weapon_sk
    cores = []
    atk_base = {'挑战者':5,'连击':5,'会心击【属性】':3,'龙属性攻击强化':3}
    
    # 检查是否已有固定的系列技能
    fixed_series = set()
    if extra_fixed:
        for sk in extra_fixed:
            if sk in fs.NO_DECO_SK:
                fixed_series.add(sk)
    
    # 如果已固定巨戟4，则不要求其他系列技能（巨戟4需4件防具，无法凑其他系列）
    has_geki4 = '巨戟龙的默示录' in fixed_series
    has_bahar3 = '霸主之魂' in fixed_series

    # 方案一/二: 武器只有黑蚀1
    if has('黑蚀龙之力') and not has('霸主之魂') and not has('火龙之力'):
        if has_geki4:
            # 已固定巨戟4，只要求攻击技能
            cores.append({**atk_base, '黑蚀龙之力':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '攻击守势':3, '弱点特效':2})
        elif has_bahar3:
            # 已固定霸主3，可再凑黑蚀2（需1件）
            cores.append({**atk_base, '黑蚀龙之力':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '巨戟龙的默示录':2, '攻击守势':3})
        else:
            # 黑蚀2需防具1件, 剩余4件可用
            cores.append({**atk_base, '黑蚀龙之力':2, '霸主之魂':3, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '霸主之魂':3, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '火龙之力':2, '巨戟龙的默示录':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '巨戟龙的默示录':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '攻击守势':3})

    # 方案三/四: 武器黑蚀1+霸主1
    elif has('黑蚀龙之力') and has('霸主之魂') and not has('火龙之力'):
        if has_geki4:
            # 已固定巨戟4，武器有黑蚀1+霸主1
            cores.append({**atk_base, '黑蚀龙之力':2, '攻击守势':3})
            cores.append({**atk_base, '无我之境':2, '攻击守势':3})
        elif has_bahar3:
            # 已固定霸主3，武器有霸主1，只需再凑霸主2件
            cores.append({**atk_base, '黑蚀龙之力':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '巨戟龙的默示录':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '无我之境':2, '攻击守势':3})
        else:
            # 黑蚀2需1件 + 霸主3需2件 = 3件, 剩余2件
            cores.append({**atk_base, '黑蚀龙之力':2, '霸主之魂':3, '巨戟龙的默示录':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '霸主之魂':3, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '黑蚀龙之力':2, '霸主之魂':3, '攻击守势':3})

    # 方案五/六: 武器火龙1+霸主1
    elif has('火龙之力') and has('霸主之魂') and not has('黑蚀龙之力'):
        if has_geki4:
            # 已固定巨戟4，武器有火龙1+霸主1
            cores.append({**atk_base, '火龙之力':2, '攻击守势':3})
            cores.append({**atk_base, '无我之境':2, '攻击守势':3})
        elif has_bahar3:
            # 已固定霸主3，武器有霸主1，只需再凑霸主2件+火龙1件
            cores.append({**atk_base, '火龙之力':2, '巨戟龙的默示录':2, '攻击守势':3})
            cores.append({**atk_base, '火龙之力':2, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '火龙之力':2, '攻击守势':3})
        else:
            # 火龙2需1件 + 霸主3需2件 = 3件, 剩余2件
            cores.append({**atk_base, '火龙之力':2, '霸主之魂':3, '巨戟龙的默示录':2, '攻击守势':3})
            cores.append({**atk_base, '火龙之力':2, '霸主之魂':3, '无我之境':2, '攻击守势':3})
            cores.append({**atk_base, '火龙之力':2, '霸主之魂':3, '攻击守势':3})

    # 带广域化的方案(方案二/四/五)需要更精简的core, 因为广域化占用珠位
    if is_wide:
        # 过滤: 保留最精简的cores, 去掉过于饱满的
        filtered = []
        for c in cores:
            # 计算非atk_base的额外技能数量
            extra = {k: v for k, v in c.items() if k not in atk_base}
            # 带广域化时最多允许3个额外核心技能
            if len(extra) <= 3:
                filtered.append(c)
        if filtered:
            cores = filtered

    return cores


PLAN_CFGS = [
    ('方案一:黑蚀1',           {'黑蚀龙之力': 1}, {}),
    ('方案二:黑蚀1+广域5',      {'黑蚀龙之力': 1}, {'广域化': 5}),
    ('方案三:黑蚀1+霸主1',      {'黑蚀龙之力': 1, '霸主之魂': 1}, {}),
    ('方案四:黑蚀1+霸主1+广域5', {'黑蚀龙之力': 1, '霸主之魂': 1}, {'广域化': 5}),
    ('方案五:火龙1+霸主1+广域5', {'火龙之力': 1, '霸主之魂': 1}, {'广域化': 5}),
    ('方案六:火龙1+霸主1',      {'火龙之力': 1, '霸主之魂': 1}, {}),
]


def verify_series(result, weapon_sk, target_skills=None, extra_fixed=None):
    """验证选出的装备是否满足目标系列/组合技能件数
    
    只验证目标要求的技能件数，忽略防具附赠的其他系列技能。
    """
    if not result: return False
    pieces = result.get('pieces', [])
    skills = result.get('skills', {})
    series_actual = {}
    for p in pieces:
        for sk_name in p.get('skills', {}):
            if sk_name in fs.NO_DECO_SK:
                series_actual[sk_name] = series_actual.get(sk_name, 0) + 1
    check_set = set(target_skills) if target_skills else set()
    check_set.update(weapon_sk.keys())
    # 加入固定技能中的系列技能
    if extra_fixed:
        for sk in extra_fixed:
            if sk in fs.NO_DECO_SK:
                check_set.add(sk)
    for sk_name in list(check_set):
        if sk_name not in fs.NO_DECO_SK:
            continue
        lv = skills.get(sk_name, 0)
        if lv <= 0:
            continue
        need_pieces = 4 if lv >= 4 else (3 if sk_name in fs.GROUP_SK else 2)
        weapon_prov = 1 if sk_name in weapon_sk else 0
        actual = series_actual.get(sk_name, 0) + weapon_prov
        if actual < need_pieces:
            return False
    return True


def search_for_plan(plan_cfg):
    label, weapon_sk, extra_fixed = plan_cfg
    is_wide = '广域化' in extra_fixed
    cores = make_core_for_plan(weapon_sk, is_wide=is_wide, extra_fixed=extra_fixed)
    best = None
    total_t = 0.0
    attempts = 0
    verified = 0

    for guard_lv in [3, 2]:
        for spirit_lv in [3, 2, 0]:
            fixed_base = dict(BASE_FIXED_MIN)
            fixed_base['格挡性能'] = guard_lv
            if spirit_lv > 0:
                fixed_base['精神抖擞'] = spirit_lv
            fixed_base.update(extra_fixed)
            fixed_base.update(weapon_sk)

            for idx, core in enumerate(cores):
                fs_sk = dict(fixed_base)
                combo_sk = {}
                for wk, wv in weapon_sk.items():
                    combo_sk[wk] = wv
                for ck, cv in core.items():
                    fs_sk[ck] = max(fs_sk.get(ck, 0), cv)

                t0 = time.time()
                attempts += 1
                try:
                    r = fs.dfs_search(fs.charm_pool, fs_sk, combo_sk, 0,
                                      max_results=3, timeout_s=2.0, quiet=True)
                except:
                    r = None
                dt = time.time() - t0; total_t += dt
                if r:
                    target_series = set(weapon_sk.keys())
                    for ck_name in core:
                        if ck_name in fs.NO_DECO_SK:
                            target_series.add(ck_name)
                    for cand in r:
                        if cand.get('pract', 0) > 0 and verify_series(cand, weapon_sk, target_series, extra_fixed):
                            verified += 1
                            if best is None or cand['pract'] > best['pract']:
                                best = dict(cand)
                                best['_cfg'] = {
                                    'guard_lv': guard_lv, 'spirit_lv': spirit_lv,
                                    'core_src': f'core#{idx}',
                                    'core_skills': dict(core),
                                }
            # 不提前break，遍历所有guard/spirit/core组合找真正最高伤害

    return best, total_t, attempts, verified


def print_detail(best, plan_cfg):
    if not best: return
    weapon_sk = plan_cfg[1]
    
    # 分离防具和护石
    armors = [p for p in best['pieces'] if p.get('part_idx', 5) < 5]
    charms = [p for p in best['pieces'] if p.get('part_idx', 5) >= 5]
    
    part_names_cn = ['头', '身', '手', '腰', '腿']
    
    print(f"\n  ── 配装明细 ──")
    print(f"  防具:")
    for p in armors:
        pi = p.get('part_idx', 0)
        slot_str = '[' + ','.join(str(s) for s in p.get('slots',[])) + ']'
        sk_str = ', '.join(f'{k}v{v}' for k,v in p.get('skills',{}).items() if v>0)
        print(f"    {part_names_cn[pi]}: {p['name']} {slot_str} 技能: {sk_str}")
    
    if charms:
        c = charms[0]
        c_sk = c.get('skills', {})
        c_sk_str = ', '.join(f'{k}v{v}' for k,v in c_sk.items() if v>0)
        c_as = c.get('slots', [])
        c_ws = c.get('weapon_slots', [])
        print(f"  护石: 技能[{c_sk_str}] 防具孔{c_as} 武器孔{c_ws}")

    # 系列技能验证
    series_actual = {}
    for p in armors:
        for sk_name in p.get('skills', {}):
            if sk_name in fs.NO_DECO_SK:
                series_actual[sk_name] = series_actual.get(sk_name, 0) + 1
    sk = {k:v for k,v in best['skills'].items() if v>0}
    series_in_sk = {k:v for k,v in sk.items() if k in fs.NO_DECO_SK}
    if series_in_sk:
        print(f"  系列技能验证:")
        for k,v in series_in_sk.items():
            need_p = 4 if v >= 4 else (3 if k in fs.GROUP_SK else 2)
            wprov = 1 if k in weapon_sk else 0
            actual_p = series_actual.get(k, 0) + wprov
            ok = "[OK]" if actual_p >= need_p else "[NO]"
            print(f"    {k}: Lv{v} 需{need_p}件(武器{wprov}+防具{series_actual.get(k,0)})={actual_p} {ok}")

    # 装饰品
    decos = best.get('deco_used',[])
    if decos and isinstance(decos[0], dict):
        dnames=[d.get('name','?') for d in decos]
    else:
        dnames=list(decos)
    dc=Counter(dnames); dstr=", ".join(f"{k}×{v}" for k,v in dc.items())
    print(f"  装饰品: {dstr}")
    
    # 核心技能展示(只显示有实际上限的伤害相关技能)
    core_ln=""
    for k in DAMAGE_SKILLS:
        if k in sk:
            cap=fs.SKILL_CAPS.get(k, 0)
            lv = min(sk[k], cap) if cap > 0 else sk[k]
            if cap > 0 and lv > 0:
                core_ln += f"{k}:{lv}/{cap}  "
    if core_ln:
        print(f"  核心技能: {core_ln}")
    
    # 其他技能(只显示有实际上限的)
    other=[(k,v) for k,v in sk.items() if k not in DAMAGE_SKILLS and v>0]
    other_display = []
    for k,v in other:
        cap = fs.SKILL_CAPS.get(k, 0)
        lv = min(v, cap) if cap > 0 else v
        if cap > 0 and lv > 0:
            other_display.append(f"{k}:{lv}/{cap}")
    if other_display:
        print(f"  其他技能: {'  '.join(other_display)}")

    # ====== 详细伤害计算 ======
    skl = best['skills']
    def cl(sk, cap): return min(skl.get(sk,0), cap)
    chal=cl('挑战者',5); burst=cl('连击',5); muzu=cl('无伤',5)
    weak=cl('弱点特效',5); furue=cl('精神抖擞',3); rikikai=cl('力量解放',5)
    super_lv=cl('超会心',5); ecrit=cl('会心击【属性】',3); migo=cl('无我之境',3)
    counter=cl('逆袭',3); atk=cl('攻击',5); kanken=cl('看破',5)
    dragon=cl('龙属性攻击强化',3); oguard=cl('攻击守势',3)
    coal=cl('因祸得福',3); absorb=cl('属性吸收',3)
    fire_dragon=cl('火龙之力',4); bahar=cl('霸主之魂',3)
    geki=cl('巨戟龙的默示录',4); kyozou=cl('凶爪龙之力',4)
    kuroshoku=cl('黑蚀龙之力',4)
    from fast_search_v3 import (W_ATK,W_CRT,W_ELE,PERM_ATK,BAHAR_MUL,ATK_MUL,ATK_VAL,
        DRAGON_ELE,GEKI_MUL,GEKI_ADD,COAL_ELE,UCSG,ABSORB_ELE,ABSORB_COV,
        OGUARD_COV,UCOU,UM,URE,UR,URK,UW,UF,OFF_GUARD,COUNTER_ATK,MUZ_ATK,
        BURST_ATK,BURST_ELE,CHAL_ATK,CRIT_VAL,SUPER_CRIT,ELEM_CRIT,FIRE_DRAGON_DMG,
        WP, TMV, WE, TEM)
    ecb=ELEM_CRIT[ecrit]; scb=SUPER_CRIT[super_lv]
    bahar_mul = BAHAR_MUL if bahar>=3 else 1.0
    atk_mul = ATK_MUL[atk]
    d_mul=DRAGON_ELE[dragon][1]; d_add=DRAGON_ELE[dragon][0]
    geki_mul=GEKI_MUL[geki]; geki_add=GEKI_ADD[geki]
    coal_expect = 1.0 + (COAL_ELE[coal]-1.0)*UCSG if coal>0 else 1.0
    absorb_add = ABSORB_ELE[absorb]*ABSORB_COV
    kyozou_atk = 8 if kyozou>=2 else 0
    
    print(f"\n  ── 详细伤害计算 ──")
    print(f"  [Step 1 面板] W_ATK={W_ATK}(面板,不含攻击技能) W_CRT={W_CRT}% W_ELE={W_ELE} PERM_ATK=+{PERM_ATK}(护符6+猫饭5, 技能加区)")
    print(f"  [Step 2 技能系数]")
    print(f"    攻击Lv{atk}: +{ATK_VAL[atk]}(加区) ×{atk_mul}(面板)  超心Lv{super_lv}: scb={scb}  属会Lv{ecrit}: ecb={ecb}")
    print(f"    龙强化Lv{dragon}: ×{d_mul}+{d_add}  霸主Lv{bahar}: ×{bahar_mul}  巨戟Lv{geki}: ×{geki_mul}+{geki_add}")
    print(f"    无伤Lv{muzu}: +{MUZ_ATK[muzu]} UM={UM}  连击Lv{burst}: 攻+{BURST_ATK[burst]}属+{BURST_ELE[burst]} URE={URE}")
    print(f"    挑战Lv{chal}: 攻+{CHAL_ATK[chal]}会+{CRIT_VAL['挑战者'][chal]}% UR={UR}  弱特Lv{weak}: +{CRIT_VAL['弱点特效'][weak]}% UW={UW}")
    print(f"    精神Lv{furue}: +{CRIT_VAL['精神抖擞'].get(furue,0)}% UF={UF}  攻守Lv{oguard}: ×{OFF_GUARD[oguard]} OGUARD_COV={OGUARD_COV}")
    print(f"    逆袭Lv{counter}: +{COUNTER_ATK[counter]} UCOU={UCOU}  看破Lv{kanken}: +{CRIT_VAL['看破'].get(kanken,0)}%  无我Lv{migo}: +{CRIT_VAL['无我之境'].get(migo,0)}%")
    if kuroshoku>=2 and migo>=3:
        print(f"    黑蚀Lv{kuroshoku}+无我Lv{migo}: 黑蚀+无我状态(会心+25%, 60%覆盖)")
    elif kuroshoku>=2:
        print(f"    黑蚀Lv{kuroshoku}: 黑蚀状态(会心+15%, 50%覆盖)")
    else:
        print(f"    黑蚀Lv{kuroshoku}: 未激活(需≥2)")
    print(f"    火龙Lv{fire_dragon}: 固定伤+{FIRE_DRAGON_DMG.get(fire_dragon,0)}")
    
    states=[]
    if chal>0 or geki>0: states.append(('rage',UR))
    if burst>0: states.append(('rengeki',URE))
    if muzu>0: states.append(('mukizu',UM))
    if rikikai>0: states.append(('rikikai',URK))
    if weak>0: states.append(('weak',UW))
    if furue>0: states.append(('furue',UF))
    if counter>0: states.append(('counter',UCOU))
    if oguard>0: states.append(('oguard',OGUARD_COV))
    if kuroshoku>=2 and migo>=3:
        states.append(('kuroshoku_migo',0.60))
    elif kuroshoku>=2:
        states.append(('kuroshoku',0.50))
    cn_list=[STATE_CN[s[0]] for s in states]
    PC_R=WP*0.45*(TMV/100); EC_R=WE*0.20*(TEM/10)
    print(f"  [Step 3 状态集] 2^{len(states)}={2**len(states)}种 = {cn_list}")
    print(f"    动作系数 PC_R={PC_R:.6f}  属动系数 EC_R={EC_R:.6f}")
    
    wr=er=0.0; rows=[]
    for combo in itertools.product(*([[True,False]]*len(states))):
        pr=1.0; add_atk=PERM_ATK; add_crt=0; add_ele=0.0
        geki_mul_act=1.0; geki_add_act=0; og_act=1.0
        active=[]
        for (nm,up),act in zip(states,combo):
            pr *= up if act else (1-up)
            if not act: continue
            active.append(STATE_CN[nm])
            if nm=='rage':
                if chal>0: add_atk+=CHAL_ATK[chal]; add_crt+=CRIT_VAL['挑战者'][chal]
                if geki>0: geki_mul_act=geki_mul; geki_add_act=geki_add
            elif nm=='rengeki': add_atk+=BURST_ATK[burst]; add_ele+=BURST_ELE[burst]
            elif nm=='mukizu': add_atk+=MUZ_ATK[muzu]
            elif nm=='rikikai': add_crt+=CRIT_VAL['力量解放'][rikikai]
            elif nm=='weak': add_crt+=CRIT_VAL['弱点特效'][weak]
            elif nm=='furue': add_crt+=CRIT_VAL['精神抖擞'][furue]
            elif nm=='counter': add_atk+=COUNTER_ATK[counter]
            elif nm=='oguard': og_act=OFF_GUARD[oguard]
            elif nm=='kuroshoku': add_crt+=15
            elif nm=='kuroshoku_migo': add_crt+=25
        if atk>0: add_atk+=ATK_VAL[atk]
        if kyozou_atk>0: add_atk+=kyozou_atk
        if kanken>0: add_crt+=CRIT_VAL['看破'].get(kanken,0)
        if migo>0: add_crt+=CRIT_VAL['无我之境'].get(migo,0)
        ea=W_ATK*atk_mul*og_act*bahar_mul + add_atk
        ec=min(W_CRT+add_crt,100)
        be=W_ELE*d_mul*geki_mul_act*coal_expect + d_add + geki_add_act + add_ele + absorb_add
        cr=ec/100.0
        crit_phys=cr*scb+(1-cr); crit_elem=cr*ecb+(1-cr)
        ph=pr*ea*PC_R*crit_phys; el=pr*be*EC_R*crit_elem
        wr+=ph; er+=el
        rows.append((active,pr,ea,ec,be,ph,el))
    rows.sort(key=lambda x: -(x[5]+x[6]))
    fix_dmg=FIRE_DRAGON_DMG.get(fire_dragon,0)
    total=wr+er+fix_dmg
    print(f"  [Step 4 各状态贡献] (概率>0.5%)")
    hdr=f"    {'状态':<30} {'概率':>6} {'物攻ea':>7} {'会心':>5} {'属性be':>7} {'物理期望':>9} {'属性期望':>9} {'合计':>8}"
    print(hdr); print(f"    {'─'*83}")
    for names,pr,ea,ec,be,ph,el in rows:
        if pr<=0.005: continue
        ns="+".join(names) if names else "无"
        print(f"    {ns:<30} {pr*100:>5.2f}% {ea:>7.1f} {ec:>4.0f}% {be:>7.1f} {ph:>9.2f} {el:>9.2f} {ph+el:>8.2f}")
    print(f"  [Step 5 汇总]")
    print(f"    物理={wr:.2f} + 属性={er:.2f} + 固定={fix_dmg} = {total:.1f}  (搜索值 {best['pract']:.1f})")


# ========== 主流程：对比巨戟4 vs 霸主3 ==========
def run_all_plans(extra_fixed_skill=None):
    """运行所有方案搜索，可选添加额外固定技能"""
    results = {}
    t_all = time.time()
    for cfg in PLAN_CFGS:
        label, weapon_sk, extra_fixed = cfg
        # 合并额外固定技能
        merged_extra = dict(extra_fixed)
        if extra_fixed_skill:
            merged_extra.update(extra_fixed_skill)
        new_cfg = (label, weapon_sk, merged_extra)
        
        t0 = time.time()
        best, sch_t, att, verc = search_for_plan(new_cfg)
        t_used = time.time() - t0
        results[label] = (best, t_used, att, verc, sch_t)
    return results

def print_summary(results, extra_name, base_fixed):
    """打印汇总表"""
    print(f"\n{'='*90}")
    print(f"汇总对比表 - {extra_name}")
    print("="*90)
    hdr=f"  {'方案':<26} {'防性':>4} {'伤害':>7} {'广域':>4} {'黑蚀':>5} {'霸主':>5} {'火龙':>5} {'巨戟':>5} {'无我':>4} {'核心攻击技能':<28} {'耗时':>7}"
    print(hdr); print(f"  {'─'*110}")
    total_dmg = 0
    for cfg in PLAN_CFGS:
        label = cfg[0]
        best, t_used, att, verc, sch_t = results[label]
        if not best:
            print(f"  {label:<26} {'无解':>4} {'-':>7}")
            continue
        sk = best['skills']; cfg_d = best['_cfg']
        total_dmg += best['pract']
        flex_show = ""
        for fsk in ['超会心','攻击守势','攻击','弱点特效','看破','逆袭','无伤','无我之境']:
            lv = sk.get(fsk,0)
            if lv>0:
                base=0
                for x in [base_fixed, cfg[1], cfg[2]]:
                    base = max(base, x.get(fsk,0))
                if lv>base:
                    cap=fs.SKILL_CAPS.get(fsk,0)
                    flex_show += f"{fsk}{lv}/{cap} "
        flex_show += f"精神{sk.get('精神抖擞',0)}"
        print(f"  {label:<26} {cfg_d['guard_lv']:>4} {best['pract']:>7.1f} "
              f"{'5' if sk.get('广域化',0)>=5 else '-':>4} "
              f"{sk.get('黑蚀龙之力',0):>5} {sk.get('霸主之魂',0):>5} {sk.get('火龙之力',0):>5} "
              f"{sk.get('巨戟龙的默示录',0):>5} {sk.get('无我之境',0):>4} "
              f"{flex_show:<28} {t_used:>6.2f}s")
    return total_dmg

print("="*90)
print("固定技能组对比：巨戟4 vs 霸主3")
print("="*90)

def print_results_detail(results, extra_fixed_skill):
    """打印每个有解方案的详情"""
    for cfg in PLAN_CFGS:
        label, weapon_sk, extra_fixed = cfg
        best, t_used, att, verc, sch_t = results[label]
        if not best:
            continue
        merged_extra = dict(extra_fixed)
        merged_extra.update(extra_fixed_skill)
        merged_cfg = (label, weapon_sk, merged_extra)
        cfg_d = best['_cfg']
        print(f"\n{'='*90}")
        print(f"[ {label} ]  武器技能: {weapon_sk}  额外强制: {extra_fixed}")
        print(f"{'='*90}")
        print(f"  最优: {cfg_d['core_src']}  防性{cfg_d['guard_lv']}  伤害={best['pract']:.1f}")
        print(f"  (尝试{att}次, 验证通过{verc}个, 搜索{sch_t:.2f}s, 总{t_used:.2f}s)")
        print_detail(best, merged_cfg)


# 方案A：固定巨戟龙的默示录4
print("\n" + "="*90)
print("方案A：固定技能 + 巨戟龙的默示录4")
print("="*90)
fixed_geki4 = {'巨戟龙的默示录': 4}
results_geki4 = run_all_plans(fixed_geki4)
print_results_detail(results_geki4, fixed_geki4)
total_geki4 = print_summary(results_geki4, "固定巨戟4", BASE_FIXED_MIN)

# 方案B：固定霸主之魂3
print("\n" + "="*90)
print("方案B：固定技能 + 霸主之魂3")
print("="*90)
fixed_bahar3 = {'霸主之魂': 3}
results_bahar3 = run_all_plans(fixed_bahar3)
print_results_detail(results_bahar3, fixed_bahar3)
total_bahar3 = print_summary(results_bahar3, "固定霸主3", BASE_FIXED_MIN)

# 对比结论
print("\n" + "="*90)
print("对比结论")
print("="*90)
print(f"  固定巨戟4：6方案总伤害 {total_geki4:.1f}")
print(f"  固定霸主3：6方案总伤害 {total_bahar3:.1f}")
diff = total_geki4 - total_bahar3
if diff > 0:
    print(f"  结论：固定巨戟4更优，总伤害高 {diff:.1f}")
else:
    print(f"  结论：固定霸主3更优，总伤害高 {-diff:.1f}")

# 详细输出最优方案
for section_name, results, fixed_sk in [
    ("固定巨戟4", results_geki4, fixed_geki4),
    ("固定霸主3", results_bahar3, fixed_bahar3),
]:
    print("\n" + "="*90)
    print(f"最优方案详细计算（{section_name}）")
    print("="*90)
    best_label = max(results.keys(), key=lambda k: results[k][0]['pract'] if results[k][0] else 0)
    best, t_used, att, verc, sch_t = results[best_label]
    if best:
        cfg = next(c for c in PLAN_CFGS if c[0] == best_label)
        merged_cfg = (cfg[0], cfg[1], {**cfg[2], **fixed_sk})
        cfg_d = best['_cfg']
        print(f"  最优方案: {best_label}")
        print(f"  最优: {cfg_d['core_src']}  防性{cfg_d['guard_lv']}  伤害={best['pract']:.1f}")
        print(f"  (尝试{att}次, 验证通过{verc}个, 搜索{sch_t:.2f}s, 总{t_used:.2f}s)")
        print_detail(best, merged_cfg)
    else:
        print(f"  {section_name} 所有方案均无解")
