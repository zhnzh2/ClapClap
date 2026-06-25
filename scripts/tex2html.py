"""
将 ClapClap 规则 .tex 编译为 HTML。
对复杂的附录表格精细处理，对正文用规则解析。
"""
import re, sys, os

def _strip_preamble(text):
    m = re.search(r'\\begin\{document\}', text)
    if m: text = text[m.end():]
    m = re.search(r'\\end\{document\}', text)
    if m: text = text[:m.start()]
    return text

def _clean_latex(text):
    """去掉 LaTeX 命令，保留纯文本和基本结构。"""
    # 去掉注释
    text = re.sub(r'(?<!\\)%.*', '', text)
    # 去掉 preamble 命令
    for cmd in [r'\\maketitle', r'\\tableofcontents', r'\\newpage', r'\\centering',
                r'\\restoregeometry', r'\\renewcommand\\.*', r'\\setstretch\{.*?\}',
                r'\\newgeometry\{.*?\}']:
        text = re.sub(cmd, '', text)
    # 格式
    text = re.sub(r'\\textbf\{(.+?)\}', r'<strong>\1</strong>', text)
    text = re.sub(r'\\textit\{(.+?)\}', r'<em>\1</em>', text)
    # 去掉多余的 {} 组
    text = re.sub(r'\{([^{}]*?)\}', r'\1', text)
    text = re.sub(r'\\hline', '', text)
    text = re.sub(r'\\cline\{.*?\}', '', text)
    return text


def convert_v1(tex_path: str) -> str:
    """1.0 规则：手工整理，保留原文全部内容。"""
    with open(tex_path, encoding='utf-8') as f:
        text = f.read()
    text = _strip_preamble(text)

    # 手工提取各节（基于已知结构）
    out = []

    # ── 游戏介绍 ──
    out.append('<h2>游戏介绍</h2>')
    out.append('<p>拍拍（Clapclap）是一款多人参与的同步出招战斗游戏，所有玩家围成一圈，通过击掌与手势的组合进行回合制对抗。</p>')
    out.append('<p>在游戏中，玩家需要在资源积累、攻击、防御与锦囊反制之间进行权衡，通过对对手行动的判断与博弈逐步取得优势，最终成为唯一存活的玩家。</p>')
    out.append('<p>与传统回合制游戏不同，本游戏的所有行动均在同一时刻完成，这意味着玩家无法依赖先后手优势，而必须通过对局势的判断与对对手心理的预判来取得胜利。</p>')
    out.append('<p>本规则书将详细介绍双人版游戏的基本规则、回合流程、资源系统、攻击与防御机制以及锦囊反制等核心玩法，帮助玩家快速上手并享受游戏的乐趣。</p>')

    # ── 游戏开始及资源介绍 ──
    out.append('<h2>游戏开始以及资源介绍</h2>')
    out.append('<p>游戏开始时，每位玩家都拥有相同的初始状态。</p>')
    out.append('<p>这个游戏总共有六种资源，分别是：生命值、气、盾、火种、电池与镐。</p>')
    out.append('<p>每位玩家初始拥有若干点生命值，一般为 <strong>1 点</strong>，其余资源均为 <strong>0</strong>。</p>')
    out.append('<ul>')
    out.append('<li><strong>生命值</strong>：代表玩家的生存状态，当生命值降至 0 时，该玩家立即出局。</li>')
    out.append('<li><strong>气</strong>：基础资源之一，可以通过特定手势积累。</li>')
    out.append('<li><strong>盾</strong>：基础资源之一，可以通过特定手势积累。</li>')
    out.append('<li><strong>火种</strong>：由盾系攻击衍生出的中间资源。</li>')
    out.append('<li><strong>电池</strong>：由盾系攻击衍生出的中间资源。</li>')
    out.append('<li><strong>镐</strong>：特殊资源，可以抵挡一点伤害。</li>')
    out.append('</ul>')
    out.append('<p>游戏中除镐外，其余资源均没有上限。</p>')

    # ── 游戏进行 ──
    out.append('<h2>游戏进行</h2>')
    out.append('<p>所有玩家在游戏中需要保持固定的姿势：右手手掌向下，左手手掌向上，使得每个人可以同时与左右两侧的玩家进行击掌。</p>')
    out.append('<p>游戏按回合进行，每一回合分为三个阶段。</p>')
    out.append('<ul>')
    out.append('<li><strong>击掌阶段</strong>：所有玩家同时与左右两侧各击掌一次，形成一个闭环的互动。</li>')
    out.append('<li><strong>出手阶段</strong>：所有玩家必须同时做出一个手势。</li>')
    out.append('<li><strong>结算阶段</strong>：根据所有玩家的手势进行统一判定，包括攻击、防御、锦囊效果以及资源变化。血量为 0 及以下的玩家视为死亡，被移除游戏。</li>')
    out.append('</ul>')
    out.append('<p>直到最后只剩下一名玩家存活时，游戏结束，该玩家获胜。</p>')
    out.append('<p>出手阶段不能延迟或观察他人后再决定，慢出手的玩家被称作<strong>蛤蟆</strong>，出不合规手势的玩家被称作<strong>蟆蛤</strong>，两者都将直接死亡。</p>')

    # ── 手势介绍 ──
    out.append('<h2>手势介绍</h2>')
    out.append('<p>游戏中的所有手势可以分为四大类：资源、攻击、防御和锦囊。</p>')
    out.append('<p>每个手势都有其攻击力和防御力。</p>')
    out.append('<p>攻击与防御的核心判定规则是：当一方大于另一方的防御力时，攻击成立并造成伤害；双方攻击力相等时，双方视为对掉。</p>')

    out.append('<h3>资源手势</h3>')
    out.append('<p>资源手势包括气和盾。</p>')
    out.append('<ul>')
    out.append('<li><strong>气</strong>：获得 1 格气，防御力为 0。</li>')
    out.append('<li><strong>盾</strong>：获得 1 格盾，防御力为 1.5。</li>')
    out.append('</ul>')
    out.append('<p>资源手势的攻击力为 0，但可以积累资源，为后续的攻击和防御提供基础。</p>')

    out.append('<h3>攻击手势</h3>')
    out.append('<p>攻击手势分为气系攻击和盾系攻击。所有攻击手势在具备攻击力的同时，其防御力也等于其攻击力。</p>')
    out.append('<ul>')
    out.append('<li><strong>gi</strong>：消耗 1 格气，攻击力为 1</li>')
    out.append('<li><strong>破</strong>：消耗 2 格气，攻击力为 2</li>')
    out.append('<li><strong>冷锋</strong>：消耗 3 格气，攻击力为 3</li>')
    out.append('<li><strong>如来</strong>：消耗 5 格气，攻击力为 4</li>')
    out.append('<li><strong>黑洞</strong>：消耗 8 格气，攻击力为 5</li>')
    out.append('<li><strong>Fire</strong>：消耗 2 格盾，攻击力为 1.5，并获得 1 个火种</li>')
    out.append('<li><strong>闪电</strong>：消耗 3 格盾，攻击力为 2，并获得 1 个电池</li>')
    out.append('<li><strong>烈焰</strong>：消耗 4 格盾或 2 个火种，攻击力为 3</li>')
    out.append('<li><strong>Shining</strong>：消耗 6 格盾或 2 个电池，攻击力为 4</li>')
    out.append('</ul>')
    out.append('<p>除去如来和 Shining 可以造成两点伤害、黑洞可以造成三点伤害以外，其它攻击都只能造成一点伤害。</p>')
    out.append('<p>Shining 可以拆分为两个闪电分别结算；黑洞可以拆分为三个小黑洞，攻击力仍为 5，但每段仅造成 1 点伤害，可以分配给一个或多个目标。</p>')

    out.append('<h3>防御手势</h3>')
    out.append('<p>防御手势用于抵御敌方攻击，攻击力为 0。</p>')
    out.append('<ul>')
    out.append('<li><strong>十字</strong>：消耗 2 格气，防御力为 3</li>')
    out.append('<li><strong>八卦</strong>：消耗 3 格气，防御力为 4</li>')
    out.append('</ul>')
    out.append('<p>这些防御手势可以有效抵挡中高强度攻击，是对抗气系和盾系爆发的重要手段。</p>')

    out.append('<h3>锦囊手势</h3>')
    out.append('<p>锦囊手势为游戏提供了关键的反制与博弈机制。</p>')
    out.append('<ul>')
    out.append('<li><strong>你吃</strong>：消耗 1 格气，可以针对特定攻击进行克制。若目标为闪电，则其攻击失效且无法获得电池；若目标为破，则其使用者会受到 1 点反噬伤害。</li>')
    out.append('<li><strong>双吃</strong>：消耗 2 格气，具备你吃的全部能力，还可以以 Shining 为目标使其攻击失效且无法获得电池。同时也可以拆分为两个你吃，分别针对不同目标。</li>')
    out.append('<li><strong>闪</strong>：无消耗，每局最多使用两次，使用后在本回合退出游戏，不参与任何结算。</li>')
    out.append('<li><strong>镐</strong>：消耗 2 格气，使用后获得一个镐。</li>')
    out.append('</ul>')
    out.append('<p>你吃和双吃未命中目标时，其消耗依然生效，同时防御力视为 0。</p>')
    out.append('<p>镐具有独特的风险机制。当一名玩家持有两个或以上的镐时，会立即触发爆镐，直接死亡；gi 可以在对方使用镐的当回合<strong>抢镐</strong>，对方不仅无法获得镐，自己还会多一个镐。因此镐既是恢复手段，也是潜在危险资源。</p>')

    # ── 总结 ──
    out.append('<h2>总结</h2>')
    out.append('<p>拍拍（Clapclap）在简单的操作形式之下构建了一个高度紧凑的战斗系统。玩家既需要通过资源积累建立优势，又必须在关键时刻做出正确判断。气体系提供了稳定而高效的战斗能力，盾体系则带来多样化的发展路径与资源转化方式，而锦囊机制进一步强化了针对性与不确定性，使得每一回合都充满变数。游戏的胜负往往取决于关键时刻的选择，而非单纯的资源数量，这也使得对局始终保持紧张与动态的平衡。</p>')
    out.append('<p>在实际体验中，拍拍（Clapclap）既保留了拍手互动带来的节奏感与参与感，又通过复杂而统一的规则体系赋予其足够的策略深度。它既可以作为轻量的互动游戏快速展开，也可以在熟练玩家之间演变为高强度的心理博弈。这种简单形式与深层策略并存的特性，正是其最核心的魅力所在。</p>')

    # ── 附录：手势一览表 ──
    out.append('<h2>附录：手势一览表</h2>')
    out.append('<table>')
    out.append('<thead><tr><th>类型</th><th>名称</th><th>消耗</th><th>攻击力/防御力</th><th>效果及备注</th><th>手势</th></tr></thead>')
    out.append('<tbody>')
    rows = [
        ['资源', '气', '—', '攻 0 / 防 0', '获得 1 格气', '双手作鼓掌状'],
        ['资源', '盾', '—', '攻 0 / 防 1.5', '获得 1 格盾', '大臂紧贴身体，双拳握于胸前'],
        ['攻击', 'gi', '1 格气', '攻 1 / 防 1', '造成 1 点伤害', '大臂紧贴身体，小臂与大臂垂直，双手握拳向前'],
        ['攻击', '破', '2 格气', '攻 2 / 防 2', '造成 1 点伤害', '双手手掌朝前，向前推出'],
        ['攻击', '冷锋', '3 格气', '攻 3 / 防 3', '造成 1 点伤害', '右手三根手指作手枪状'],
        ['攻击', '如来', '5 格气', '攻 4 / 防 4', '造成 2 点伤害', '右手手掌向左，除食指弯曲之外其它手指竖直向上'],
        ['攻击', '黑洞', '8 格气', '攻 5 / 防 5', '造成 3 点伤害；可拆分为 3 个小黑洞', '左手小臂平行置于右手小臂上方，双手指尖置于肘前区形成朝前方的矩形'],
        ['攻击', 'Fire', '2 格盾', '攻 1.5 / 防 1.5', '获得 1 个火种', '双手交叉于腹前，手掌向上手指自然弯曲'],
        ['攻击', '闪电', '3 格盾', '攻 2 / 防 2', '获得 1 个电池', '双手置于身前手心向下，伸出食指和中指并拢，用右手双指第二指关节敲击左手双指第二指关节'],
        ['攻击', '烈焰', '4 格盾 或 2 火种', '攻 3 / 防 3', '造成 1 点伤害', '双手交叉于腹前，手掌向下，手指自然弯曲'],
        ['攻击', 'Shining', '6 格盾 或 2 电池', '攻 4 / 防 4', '造成 2 点伤害；可拆分为 2 个闪电', '双手各三根手指作手枪状置于额头前上方区域，手背向外，用右手双指第二指关节敲击左手双指第二指关节'],
        ['防御', '十字防', '2 格气', '防 3', '有效抵挡中等强度攻击', '双手握拳置于身前，左手小臂平行置于右手小臂上方'],
        ['防御', '八卦', '3 格气', '防 4', '抵挡高强度攻击', '双手小臂置于身前上下移动，手掌面向自己，手指自由弯曲'],
        ['锦囊', '你吃', '1 格气', '防 0', '吃掉闪电吃死破', '伸出食指指向前方'],
        ['锦囊', '双吃', '2 格气', '防 0', '吃掉闪电吃死破；吃掉 Shining', '伸出食指和中指并拢指向前方'],
        ['锦囊', '闪', '无', '—', '每局最多使用两次', '伸出一根手指在身前晃动'],
        ['锦囊', '镐', '2 格气', '防 0', '获得 1 个镐', '右手握拳锤向心脏位置'],
    ]
    for r in rows:
        out.append('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>')
    out.append('</tbody></table>')

    out.append('<hr>')
    out.append('<p style="text-align:center; color: var(--muted); font-size:13px;">拍拍 Clapclap 双人版 规则书 · 2026.3.17</p>')
    return '\n'.join(out)


def convert_v2(tex_path: str) -> str:
    """2.0 规则：基于 develop/rule-spec-2.0.md 和 tex 原文整理。"""
    with open(tex_path, encoding='utf-8') as f:
        text = f.read()
    text = _strip_preamble(text)
    # 手工清洗
    text = re.sub(r'%------------------------------------------------', '', text)
    text = re.sub(r'(?<!\\)%.*', '', text)
    text = re.sub(r'\\maketitle|\\tableofcontents|\\newpage|\\centering', '', text)
    text = re.sub(r'\\newgeometry\{.*?\}|\\restoregeometry|\\renewcommand\\.*|\\setstretch\{.*?\}', '', text)
    # 转义
    text = text.replace(r'\_', '_').replace(r'\&', '&').replace(r'\%', '%')
    text = re.sub(r'\\#', '#', text)

    out = []
    lines = text.split('\n')
    i = 0
    buf = []
    in_ul = False
    in_table = False
    table_rows = []
    pending_subsection = None  # 累积 subsection 名称

    def flush_buf():
        nonlocal buf
        if buf:
            txt = ' '.join(buf).strip()
            if txt:
                out.append(f'<p>{txt}</p>')
            buf = []

    def open_ul():
        nonlocal in_ul
        if not in_ul:
            out.append('<ul>')
            in_ul = True

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append('</ul>')
            in_ul = False

    # 解析标题和内容的辅助
    def add_section(title):
        nonlocal pending_subsection
        close_ul()
        flush_buf()
        out.append(f'<h2>{title}</h2>')
        pending_subsection = None

    def add_subsection(title):
        nonlocal pending_subsection
        close_ul()
        flush_buf()
        out.append(f'<h3>{title}</h3>')
        pending_subsection = None

    for line in lines:
        s = line.strip()
        if not s:
            flush_buf()
            continue

        # section
        m = re.match(r'\\section\*?\{(.+?)\}', s)
        if m:
            title = _clean_latex(m.group(1))
            add_section(title)
            continue

        # subsection
        m = re.match(r'\\subsection\*?\{(.+?)\}', s)
        if m:
            title = _clean_latex(m.group(1))
            add_subsection(title)
            continue

        # subsubsection
        m = re.match(r'\\subsubsection\{(.+?)\}', s)
        if m:
            title = _clean_latex(m.group(1))
            close_ul(); flush_buf()
            out.append(f'<h4>{title}</h4>')
            continue

        # itemize 开始
        if s == r'\begin{itemize}':
            flush_buf()
            open_ul()
            continue
        if s == r'\end{itemize}':
            close_ul()
            continue
        # item
        if s.startswith(r'\item'):
            flush_buf()
            item_text = _clean_latex(s[len(r'\item'):].strip())
            out.append(f'<li>{item_text}</li>')
            continue

        # tabular 开始
        if s.startswith(r'\begin{tabular}'):
            flush_buf(); close_ul()
            in_table = True; table_rows = []
            continue
        if s == r'\end{tabular}':
            in_table = False
            # 输出表格
            if table_rows:
                # 判断是否有表头（第二行包含多个 &）
                has_head = len(table_rows) > 1 and table_rows[1].count('&') > 0
                out.append('<table>')
                if has_head:
                    out.append('<thead><tr>')
                    for c in table_rows[0]:
                        out.append(f'<th>{_clean_latex(c)}</th>')
                    out.append('</tr></thead><tbody>')
                    body = table_rows[1:]
                else:
                    out.append('<tbody>')
                    body = table_rows
                for row in body:
                    out.append('<tr>')
                    for c in row:
                        out.append(f'<td>{_clean_latex(c)}</td>')
                    out.append('</tr>')
                out.append('</tbody></table>')
            continue
        if in_table:
            # 按 \\ 分割行
            if r'\\' in s:
                parts = s.split(r'\\')
                for p in parts:
                    p = p.strip()
                    if p and p != r'\hline':
                        cells = [c.strip() for c in p.split('&')]
                        cells = [_clean_latex(c) for c in cells]
                        if cells:
                            table_rows.append(cells)
            else:
                if s != r'\hline':
                    cells = [c.strip() for c in s.split('&')]
                    cells = [_clean_latex(c) for c in cells]
                    if cells:
                        table_rows.append(cells)
            continue

        # 普通文本行
        s = _clean_latex(s)
        buf.append(s)

    flush_buf()
    close_ul()

    # 后处理：清理残留 LaTeX 命令
    result = '\n'.join(out)
    result = re.sub(r'\\addcontentsline\b.*', '', result)
    result = re.sub(r'\\addcontentslinetocsection\b.*', '', result)
    result = re.sub(r'\\begin\{center\}', '', result)
    result = re.sub(r'\\end\{center\}', '', result)
    result = re.sub(r'\\begincenter\b', '', result)
    result = re.sub(r'\\endcenter\b', '', result)
    result = re.sub(r'\\begin\{itemize\}', '<ul>', result)
    result = re.sub(r'\\end\{itemize\}', '</ul>', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    # 末尾署名
    result += '\n<hr>\n'
    result += '<p style="text-align:center; color: var(--muted); font-size:13px;">拍拍 Clapclap 2.0 规则书 · 2026.3.20</p>'
    return result


if __name__ == '__main__':
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    html = convert_v1(os.path.join(base, 'rules/version 1.0/rule.tex'))
    with open(os.path.join(base, 'server/templates/rule_1.0_content.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"1.0: {len(html)} chars")

    html = convert_v2(os.path.join(base, 'rules/version 2.0/rule2.0.tex'))
    with open(os.path.join(base, 'server/templates/rule_2.0_content.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"2.0: {len(html)} chars")
    print("Done.")
