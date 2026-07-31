#!/usr/bin/env python3
"""MHWilds 配装搜索 GUI 服务器

使用 Python 内置 http.server 模块，无需额外依赖。
运行: python3 gui_server.py [端口]
默认端口: 8765
"""
import json
import sys
import os
import time
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

import fast_search_v3 as fs
from calc_v8_final import (
    PLAN_CFGS, BASE_FIXED_MIN, DAMAGE_SKILLS,
    make_core_for_plan, verify_series, search_for_plan,
    run_all_plans, print_summary, print_results_detail
)

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(SERVER_DIR, 'index.html')
SKILLS_DATA_PATH = os.path.join(SERVER_DIR, 'skills_data.json')

_lock = threading.Lock()

_SKILLS_DATA = None
def _load_skills_data():
    global _SKILLS_DATA
    if _SKILLS_DATA is None:
        try:
            with open(SKILLS_DATA_PATH, 'r', encoding='utf-8') as f:
                _SKILLS_DATA = json.load(f)
        except Exception:
            _SKILLS_DATA = {}
    return _SKILLS_DATA

# 技能分类
SKILL_CATEGORIES = {
    '攻击·会心': ['攻击', '看破', '超会心', '弱点特效', '挑战者', '连击', '无伤', '攻击守势', '巧击', '因祸得福', '精神抖擞', '无我之境', '力量解放', '攻势', '逆袭'],
    '属性·特殊': ['龙属性攻击强化', '火属性攻击强化', '水属性攻击强化', '冰属性攻击强化', '雷属性攻击强化', '会心击【属性】', '属性吸收', '属性变换', '锁刃刺击'],
    '锋利度': ['匠', '利刃', '刚刃打磨', '心眼', '钝器能手', '达人艺'],
    '防御·生存': ['格挡性能', '格挡强化', '防御', '精灵加护', '缓冲', '耳塞', '回避性能', '火场怪力'],
    '广域·辅助': ['广域化', '满足感', '快吃', '减轻胆怯', '体术', '跑者', '强化持续'],
    '系列技能': ['巨戟龙的默示录', '火龙之力', '凶爪龙之力', '黑蚀龙之力', '泡狐龙之力', '煌雷龙之力', '海龙的涡雷', '冻峰龙之反叛', '锁刃龙之饥饿', '霸主之魂'],
    '其他': ['破坏王', '怨恨', '适应环境'],
}


def _plan_result_to_dict(best, plan_cfg, t_used, attempts, verified, sch_t):
    """将搜索结果转换为可JSON序列化的字典"""
    if not best:
        return None
    weapon_sk = plan_cfg[1]
    armors = [p for p in best['pieces'] if p.get('part_idx', 5) < 5]
    charms = [p for p in best['pieces'] if p.get('part_idx', 5) >= 5]
    part_names_cn = ['头', '身', '手', '腰', '腿']

    armor_list = []
    for p in armors:
        pi = p.get('part_idx', 0)
        armor_list.append({
            'part': part_names_cn[pi] if pi < 5 else '护石',
            'name': p['name'],
            'slots': list(p.get('slots', [])),
            'skills': {k: v for k, v in p.get('skills', {}).items() if v > 0}
        })
    charm_info = None
    if charms:
        c = charms[0]
        charm_info = {
            'name': c['name'],
            'skills': {k: v for k, v in c.get('skills', {}).items() if v > 0},
            'armor_slots': list(c.get('slots', [])),
            'weapon_slots': list(c.get('weapon_slots', []))
        }

    # 系列技能验证
    series_actual = {}
    for p in armors:
        for sk_name in p.get('skills', {}):
            if sk_name in fs.NO_DECO_SK:
                series_actual[sk_name] = series_actual.get(sk_name, 0) + 1
    series_check = []
    sk = {k: v for k, v in best['skills'].items() if v > 0}
    for k, v in sk.items():
        if k in fs.NO_DECO_SK:
            need_p = 4 if v >= 4 else (3 if k in fs.GROUP_SK else 2)
            wprov = 1 if k in weapon_sk else 0
            actual_p = series_actual.get(k, 0) + wprov
            series_check.append({
                'skill': k, 'level': v, 'need_pieces': need_p,
                'weapon_provided': wprov, 'armor_pieces': series_actual.get(k, 0),
                'actual_pieces': actual_p, 'ok': actual_p >= need_p
            })

    # 装饰品统计
    decos_used = best.get('deco_used', [])
    from collections import Counter
    if decos_used and isinstance(decos_used[0], dict):
        dnames = [d.get('name', '?') for d in decos_used]
    else:
        dnames = list(decos_used)
    deco_counts = dict(Counter(dnames))

    # 核心技能展示
    core_skills = {}
    for k in DAMAGE_SKILLS:
        if k in sk:
            cap = fs.SKILL_CAPS.get(k, 0)
            lv = min(sk[k], cap) if cap > 0 else sk[k]
            if cap > 0 and lv > 0:
                core_skills[k] = {'level': lv, 'cap': cap}

    # 其他技能
    other_skills = {}
    for k, v in sk.items():
        if k not in DAMAGE_SKILLS and v > 0:
            cap = fs.SKILL_CAPS.get(k, 0)
            lv = min(v, cap) if cap > 0 else v
            if cap > 0 and lv > 0:
                other_skills[k] = {'level': lv, 'cap': cap}

    cfg_d = best.get('_cfg', {})
    return {
        'damage': round(best.get('pract', 0), 2),
        'cfg': {
            'guard_lv': cfg_d.get('guard_lv'),
            'spirit_lv': cfg_d.get('spirit_lv'),
            'core_src': cfg_d.get('core_src'),
            'core_skills': cfg_d.get('core_skills', {})
        },
        'timing': {
            'search_time': round(sch_t, 3),
            'total_time': round(t_used, 3),
            'attempts': attempts,
            'verified': verified
        },
        'armors': armor_list,
        'charm': charm_info,
        'series_check': series_check,
        'decorations': deco_counts,
        'core_skills': core_skills,
        'other_skills': other_skills,
        'remaining_slots': {
            'armor': list(best.get('rem_a', [])),
            'weapon': list(best.get('rem_w', []))
        }
    }


class SearchHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""

    def log_message(self, format, *args):
        """抑制默认日志输出"""
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ('/', '/index.html'):
            if os.path.exists(INDEX_PATH):
                with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                    html = f.read()
                self._send_html(html)
            else:
                self._send_html('<h1>index.html 未找到，请检查文件</h1>')
            return

        if path == '/api/info':
            skills_data = _load_skills_data()
            info = {
                'skill_caps': fs.SKILL_CAPS,
                'plan_cfgs': [{'label': c[0], 'weapon_sk': c[1], 'extra_fixed': c[2]} for c in PLAN_CFGS],
                'base_fixed_min': BASE_FIXED_MIN,
                'series_names': [
                    '巨戟龙的默示录', '火龙之力', '凶爪龙之力', '黑蚀龙之力',
                    '泡狐龙之力', '煌雷龙之力', '海龙的涡雷',
                    '冻峰龙之反叛', '锁刃龙之饥饿'
                ],
                'group_skills': list(fs.GROUP_SK) if fs.GROUP_SK else [],
                'weapon_skill_list': sorted(list(fs.WEAPON_SK)),
                'damage_skills': DAMAGE_SKILLS,
                'skills_data': skills_data,
                'skill_categories': SKILL_CATEGORIES,
            }
            self._send_json(info)
            return

        if path == '/api/skills':
            all_skills = {}
            for p in ['head', 'body', 'arms', 'waist', 'legs']:
                for a in fs.parts[p]:
                    for s, lv in a.get('skills', {}).items():
                        if s not in all_skills:
                            all_skills[s] = {'max_in_armor': 0, 'has_deco': False, 'cap': fs.SKILL_CAPS.get(s, 0)}
                        all_skills[s]['max_in_armor'] = max(all_skills[s]['max_in_armor'], lv)
            for c in fs.charm_pool:
                for s, lv in c.get('skills', {}).items():
                    if s not in all_skills:
                        all_skills[s] = {'max_in_armor': 0, 'has_deco': False, 'cap': fs.SKILL_CAPS.get(s, 0)}
            for dtype in ('weapon', 'armor'):
                for (sk, dt), _ in fs.deco_idx.items():
                    if dt == dtype and sk in all_skills:
                        all_skills[sk]['has_deco'] = True
            self._send_json({'skills': all_skills})
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get('Content-Length', 0))
        req_body = self.rfile.read(content_len).decode('utf-8') if content_len > 0 else '{}'
        try:
            params = json.loads(req_body) if req_body else {}
        except json.JSONDecodeError:
            params = {}

        if path == '/api/search_plan':
            return self._handle_search_plan(params)
        if path == '/api/search_all':
            return self._handle_search_all(params)
        if path == '/api/query_extra':
            return self._handle_query_extra(params)
        if path == '/api/custom_search':
            return self._handle_custom_search(params)
        if path == '/api/detail_calc':
            return self._handle_detail_calc(params)

        self._send_json({'error': 'Not found'}, 404)

    def _apply_weapon_slots(self, params):
        """Apply custom weapon slots from params, returns original WSLOTS for restoration"""
        orig_wslots = list(fs.WSLOTS)
        ws = params.get('weapon_slots')
        if ws and isinstance(ws, list) and len(ws) == 3:
            fs.WSLOTS = [max(1, min(3, int(v))) for v in ws]
        return orig_wslots

    def _handle_search_plan(self, params):
        plan_idx = params.get('plan_idx', 0)
        extra_fixed = params.get('extra_fixed', {})
        if plan_idx < 0 or plan_idx >= len(PLAN_CFGS):
            return self._send_json({'error': '无效的方案索引'}, 400)
        cfg = PLAN_CFGS[plan_idx]
        label, weapon_sk, base_extra = cfg
        merged_extra = dict(base_extra)
        merged_extra.update({k: int(v) for k, v in extra_fixed.items() if int(v) > 0})
        new_cfg = (label, weapon_sk, merged_extra)
        t0 = time.time()
        with _lock:
            best, sch_t, att, verc = search_for_plan(new_cfg)
        t_used = time.time() - t0
        result = _plan_result_to_dict(best, new_cfg, t_used, att, verc, sch_t)
        self._send_json({
            'label': label,
            'weapon_sk': weapon_sk,
            'extra_fixed': merged_extra,
            'result': result,
            'ok': result is not None
        })

    def _handle_search_all(self, params):
        extra_fixed_skill = params.get('extra_fixed_skill')
        extra_name = params.get('extra_name', '默认')
        t0 = time.time()
        with _lock:
            results = run_all_plans(extra_fixed_skill)
        t_used = time.time() - t0

        summary_rows = []
        total_dmg = 0.0
        for cfg in PLAN_CFGS:
            label = cfg[0]
            if label in results:
                best, t_plan, att, verc, sch_t = results[label]
                if best:
                    total_dmg += best.get('pract', 0)
                    sk = best['skills']
                    cfg_d = best.get('_cfg', {})
                    flex_skills = []
                    for fsk in ['超会心', '攻击守势', '攻击', '弱点特效', '看破', '逆袭', '无伤', '无我之境']:
                        lv = sk.get(fsk, 0)
                        if lv > 0:
                            base = 0
                            for x in [BASE_FIXED_MIN, cfg[1], cfg[2]]:
                                base = max(base, x.get(fsk, 0))
                            if lv > base:
                                cap = fs.SKILL_CAPS.get(fsk, 0)
                                flex_skills.append(f'{fsk}{lv}/{cap}')
                    flex_skills.append(f"精神{sk.get('精神抖擞', 0)}")
                    summary_rows.append({
                        'label': label,
                        'guard_lv': cfg_d.get('guard_lv'),
                        'damage': round(best.get('pract', 0), 1),
                        'wide': sk.get('广域化', 0) >= 5,
                        'heishi': sk.get('黑蚀龙之力', 0),
                        'bahar': sk.get('霸主之魂', 0),
                        'huolong': sk.get('火龙之力', 0),
                        'juji': sk.get('巨戟龙的默示录', 0),
                        'wuwo': sk.get('无我之境', 0),
                        'flex_skills': flex_skills,
                        'total_time': round(t_plan, 2)
                    })
                else:
                    summary_rows.append({
                        'label': label, 'damage': None, 'ok': False
                    })

        # 最佳方案详情
        best_label = max(results.keys(),
                         key=lambda k: results[k][0]['pract'] if results[k][0] else 0)
        best, best_t, best_att, best_verc, best_scht = results[best_label]
        best_cfg = next(c for c in PLAN_CFGS if c[0] == best_label)
        merged_extra_best = dict(best_cfg[2])
        merged_extra_best.update(extra_fixed_skill or {})
        merged_cfg_best = (best_cfg[0], best_cfg[1], merged_extra_best)
        best_detail = _plan_result_to_dict(best, merged_cfg_best, best_t, best_att, best_verc, best_scht) if best else None

        self._send_json({
            'extra_name': extra_name,
            'total_time': round(t_used, 2),
            'total_damage': round(total_dmg, 1),
            'summary': summary_rows,
            'best_label': best_label,
            'best_detail': best_detail
        })

    def _handle_query_extra(self, params):
        fixed_skills = params.get('fixed_skills', {})
        combo_skills = params.get('combo_skills', {})
        min_rem_armor = int(params.get('min_rem_armor', 0))
        fixed_skills = {k: int(v) for k, v in fixed_skills.items() if int(v) > 0}
        combo_skills = {k: int(v) for k, v in combo_skills.items() if int(v) > 0}

        orig_wslots = self._apply_weapon_slots(params)
        t0 = time.time()
        with _lock:
            try:
                result = fs.query_extra(fixed_skills, combo_skills, min_rem_armor, fs.charm_pool)
            except Exception as e:
                fs.WSLOTS = orig_wslots
                self._send_json({'error': f'查询出错: {e}'}, 500)
                return
        fs.WSLOTS = orig_wslots
        dt = round(time.time() - t0, 2)

        # query_extra now returns a dict with structured data
        if isinstance(result, dict):
            self._send_json({
                'result_text': result.get('result_text', ''),
                'baseline_dmg': result.get('baseline_dmg', 0),
                'baseline_wcr': result.get('baseline_wcr', 0),
                'upgrade_skills': result.get('upgrade_skills', []),
                'extra_skills': result.get('extra_skills', []),
                'slot_info': result.get('slot_info', {}),
                'slot_max': result.get('slot_max', {}),
                'time': dt,
            })
        else:
            # Fallback for old string return
            self._send_json({'result_text': str(result), 'time': dt})

    def _handle_custom_search(self, params):
        fixed_skills = params.get('fixed_skills', {})
        combo_skills = params.get('combo_skills', {})
        min_rem_armor = int(params.get('min_rem_armor', 0))
        max_results = int(params.get('max_results', 5))
        timeout_s = float(params.get('timeout_s', 3.0))

        fixed_skills = {k: int(v) for k, v in fixed_skills.items() if int(v) > 0}
        combo_skills = {k: int(v) for k, v in combo_skills.items() if int(v) > 0}

        weapon_skills_dict = {}
        for s, lv in combo_skills.items():
            weapon_skills_dict[s] = weapon_skills_dict.get(s, 0) + 1

        orig_wslots = self._apply_weapon_slots(params)
        t0 = time.time()
        with _lock:
            try:
                raw_results = fs.dfs_search(
                    fs.charm_pool, fixed_skills, combo_skills, min_rem_armor,
                    max_results=max_results, timeout_s=timeout_s, quiet=False
                )
            except Exception as e:
                fs.WSLOTS = orig_wslots
                self._send_json({'error': f'搜索出错: {e}'}, 500)
                return
        fs.WSLOTS = orig_wslots
        t_used = time.time() - t0

        results = []
        for r in raw_results[:max_results]:
            fake_cfg = ('自定义搜索', weapon_skills_dict, {})
            results.append(_plan_result_to_dict(r, fake_cfg, t_used, 1, len(raw_results), t_used))

        self._send_json({
            'count': len(results),
            'total_time': round(t_used, 2),
            'fixed_skills': fixed_skills,
            'combo_skills': combo_skills,
            'results': results
        })

    def _handle_detail_calc(self, params):
        """Calculate detailed damage breakdown for given skills"""
        fixed_skills = params.get('fixed_skills', {})
        combo_skills = params.get('combo_skills', {})
        fixed_skills = {k: int(v) for k, v in fixed_skills.items() if int(v) > 0}
        combo_skills = {k: int(v) for k, v in combo_skills.items() if int(v) > 0}

        orig_wslots = self._apply_weapon_slots(params)
        t0 = time.time()
        with _lock:
            try:
                raw_results = fs.dfs_search(
                    fs.charm_pool, fixed_skills, combo_skills, 0,
                    max_results=1, timeout_s=5.0, quiet=True
                )
            except Exception as e:
                fs.WSLOTS = orig_wslots
                self._send_json({'error': f'计算出错: {e}'}, 500)
                return
        fs.WSLOTS = orig_wslots
        t_used = time.time() - t0

        if not raw_results:
            self._send_json({'ok': False, 'error': '无可行方案'})
            return

        best = raw_results[0]
        weapon_skills_dict = {}
        for s, lv in combo_skills.items():
            weapon_skills_dict[s] = weapon_skills_dict.get(s, 0) + 1
        fake_cfg = ('详情计算', weapon_skills_dict, {})
        result = _plan_result_to_dict(best, fake_cfg, t_used, 1, 1, t_used)

        # Generate detailed damage breakdown text
        all_skills = dict(fixed_skills)
        all_skills.update(combo_skills)
        if best.get('skills'):
            for sk, lv in best['skills'].items():
                if sk not in all_skills:
                    all_skills[sk] = lv

        baseline_dmg = fs.calc_damage(fixed_skills)
        final_dmg = best.get('pract', 0)
        baseline_wcr = fs.calc_weighted_crit(fixed_skills)
        final_wcr = fs.calc_weighted_crit(best.get('skills', {}))

        detail_lines = []
        detail_lines.append(f"=== 伤害计算详情 ===")
        detail_lines.append(f"")
        detail_lines.append(f"【基线】仅固定技能:")
        detail_lines.append(f"  期望伤害: {baseline_dmg:.1f}")
        detail_lines.append(f"  加权会心: {baseline_wcr:.1f}%")
        detail_lines.append(f"")
        detail_lines.append(f"【最终方案】")
        detail_lines.append(f"  期望伤害: {final_dmg:.1f}")
        detail_lines.append(f"  加权会心: {final_wcr:.1f}%")
        detail_lines.append(f"  伤害提升: +{final_dmg - baseline_dmg:.1f} ({(final_dmg/max(baseline_dmg,1)-1)*100:.1f}%)")
        detail_lines.append(f"")
        detail_lines.append(f"【技能构成】")
        for sk, lv in sorted(all_skills.items()):
            if lv > 0:
                cap = fs.SKILL_CAPS.get(sk, 99)
                tag = "满级" if lv >= cap else f"未满级"
                detail_lines.append(f"  {sk}: Lv{lv}/{cap} ({tag})")

        self._send_json({
            'ok': True,
            'result': result,
            'detail_text': '\n'.join(detail_lines),
            'baseline_dmg': round(baseline_dmg, 1),
            'final_dmg': round(final_dmg, 1),
            'time': round(t_used, 2),
        })


def main():
    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    server = HTTPServer(('0.0.0.0', port), SearchHandler)
    print(f'MHWilds 配装搜索 GUI 已启动: http://localhost:{port}')
    print(f'按 Ctrl+C 停止服务器')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
        server.server_close()


if __name__ == '__main__':
    main()
